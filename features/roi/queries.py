import logging
import json
from typing import List, Dict, Optional, Any

from database.session import with_db_connection

logger = logging.getLogger(__name__)


def extract_geometry_from_geojson(geojson_data):
    """
    Extrai a geometria adequada do GeoJSON para armazenamento no PostGIS
    """
    if isinstance(geojson_data, str):
        try:
            geojson_data = json.loads(geojson_data)
        except json.JSONDecodeError:
            raise ValueError("GeoJSON string inválido")

    if not isinstance(geojson_data, dict):
        raise ValueError(
            "GeoJSON deve ser um dicionário ou string JSON válida")

    geom_type = geojson_data.get('type')

    if geom_type == 'FeatureCollection':
        features = geojson_data.get('features', [])
        if not features:
            raise ValueError("FeatureCollection não contém features")

        if len(features) == 1:
            geometry = features[0].get('geometry')
            if not geometry:
                raise ValueError("Feature não contém geometria")
            return json.dumps(geometry)
        else:
            geometries = []
            for feature in features:
                geom = feature.get('geometry')
                if geom:
                    geometries.append(geom)

            if not geometries:
                raise ValueError(
                    "Nenhuma geometria válida encontrada nas features")

            geometry_collection = {
                "type": "GeometryCollection",
                "geometries": geometries
            }
            return json.dumps(geometry_collection)

    elif geom_type == 'Feature':
        geometry = geojson_data.get('geometry')
        if not geometry:
            raise ValueError("Feature não contém geometria")
        return json.dumps(geometry)

    elif geom_type in ['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon', 'GeometryCollection']:
        return json.dumps(geojson_data)

    else:
        raise ValueError(f"Tipo de GeoJSON não suportado: {geom_type}")

# --- Queries CRUD ---
@with_db_connection
async def criar_roi(
    conn,
    *,
    user_id: int,
    roi_data: Dict
):
    """
    Cria uma nova ROI no banco de dados
    """
    try:
        metadata = roi_data.get('metadata', {})
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata)

        geometria_original = roi_data['geometria']
        geometria_para_postgis = extract_geometry_from_geojson(
            geometria_original)

        metadata_dict = json.loads(metadata) if isinstance(
            metadata, str) else metadata

        if isinstance(geometria_original, dict) and geometria_original.get('type') == 'FeatureCollection':
            metadata_dict['feature_collection_original'] = geometria_original
        elif isinstance(geometria_original, str):
            try:
                parsed_geom = json.loads(geometria_original)
                if parsed_geom.get('type') == 'FeatureCollection':
                    metadata_dict['feature_collection_original'] = parsed_geom
            except json.JSONDecodeError:
                pass

        metadata = json.dumps(metadata_dict)

        result = await conn.fetchrow(
            """
            INSERT INTO regiao_de_interesse 
            (user_id, nome, descricao, geometria, tipo_origem, metadata, sistema_referencia,
             nome_arquivo_original, arquivos_relacionados)
            VALUES ($1, $2, $3, ST_GeomFromGeoJSON($4), $5, $6::jsonb, 'EPSG:4326', $7, $8::jsonb)
            RETURNING roi_id, nome, ST_AsGeoJSON(geometria)::json as geometria, 
                      tipo_origem, status, data_criacao, nome_arquivo_original, metadata
            """,
            user_id,
            roi_data['nome'],
            roi_data.get('descricao', ''),
            geometria_para_postgis,
            roi_data['tipo_origem'],
            metadata,
            roi_data.get('nome_arquivo_original'),
            json.dumps(roi_data.get('arquivos_relacionados', {}))
        )
        return dict(result)
    except Exception as e:
        logger.error(f"Erro ao criar ROI: {str(e)}", exc_info=True)
        raise


@with_db_connection
async def criar_propriedade_e_talhoes(
    conn,
    *,
    user_id: int,
    property_data: Dict,
    plots_data: List[Dict],
    shp_filename: str
) -> Dict[str, Any]:
    """
    Cria uma ROI de Propriedade (pai) e várias ROIs de Talhão (filhas),
    e salva uma FeatureCollection válida e corretamente formatada nos metadados.
    """
    async with conn.transaction():
        prop_metadata = property_data.get('metadata', {})
        prop_metadata['nome_arquivo_original'] = shp_filename
        prop_metadata.pop('feature_collection_talhoes', None)

        prop_insert_query = """
        INSERT INTO regiao_de_interesse (user_id, nome, descricao, geometria, tipo_origem, metadata, sistema_referencia, nome_arquivo_original, tipo_roi, nome_propriedade)
        VALUES ($1, $2, $3, ST_GeomFromGeoJSON($4), $5, $6::jsonb, 'EPSG:4326', $7, 'PROPRIEDADE', $8)
        RETURNING roi_id, nome, data_criacao, nome_propriedade;
        """
        prop_geom_json = json.dumps(property_data['geometria'])
        created_prop = await conn.fetchrow(
            prop_insert_query, user_id, property_data['nome'], property_data['descricao'],
            prop_geom_json, 'shapefile_hierarchical', json.dumps(
                prop_metadata),
            shp_filename, property_data['nome_propriedade']
        )
        parent_roi_id = created_prop['roi_id']
        logger.info(
            f"ROI de Propriedade '{created_prop['nome']}' criada com ID: {parent_roi_id}")

        plot_insert_query = """
        INSERT INTO regiao_de_interesse (user_id, nome, descricao, geometria, tipo_origem, metadata, sistema_referencia, nome_arquivo_original, tipo_roi, nome_propriedade, nome_talhao, roi_pai_id)
        VALUES ($1, $2, $3, ST_GeomFromGeoJSON($4), $5, $6::jsonb, 'EPSG:4326', $7, 'TALHAO', $8, $9, $10);
        """
        for plot in plots_data:
            await conn.execute(
                plot_insert_query, user_id, plot['nome'], plot['descricao'], json.dumps(
                    plot['geometria']),
                'shapefile_hierarchical', json.dumps(
                    plot.get('metadata', {})), shp_filename,
                property_data['nome_propriedade'], plot['nome_talhao'], parent_roi_id
            )

        talhoes_from_db = await conn.fetch("""
            SELECT roi_id, nome_talhao, ST_AsGeoJSON(geometria) as geometria_geojson, metadata
            FROM regiao_de_interesse
            WHERE roi_pai_id = $1 AND user_id = $2 AND tipo_roi = 'TALHAO'
        """, parent_roi_id, user_id)

        features = []
        for talhao in talhoes_from_db:
            feature_properties = {
                "roi_id": talhao['roi_id'],
                "nome_talhao": str(talhao['nome_talhao'])
            }

            talhao_metadata = talhao.get('metadata')

            parsed_metadata = {}
            if isinstance(talhao_metadata, str):
                try:
                    parsed_metadata = json.loads(talhao_metadata)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Metadados do talhão ID {talhao['roi_id']} é uma string JSON malformada.")
            elif isinstance(talhao_metadata, dict):
                parsed_metadata = talhao_metadata

            feature_properties.update(parsed_metadata)

            feature = {
                "type": "Feature",
                "geometry": json.loads(talhao['geometria_geojson']),
                "properties": feature_properties
            }
            features.append(feature)

        final_feature_collection = {
            "type": "FeatureCollection", "features": features}

        await conn.execute("""
            UPDATE regiao_de_interesse
            SET metadata = metadata || jsonb_build_object('feature_collection_talhoes', $1::jsonb)
            WHERE roi_id = $2
        """, json.dumps(final_feature_collection), parent_roi_id)

        logger.info(
            f"Metadados da Propriedade ID {parent_roi_id} atualizados com a FeatureCollection completa.")

        return {"propriedade": dict(created_prop), "talhoes": [dict(t) for t in talhoes_from_db]}


@with_db_connection
async def listar_rois_usuario(
    conn,
    user_id: int,
    limit: int = 10,
    offset: int = 0,
    apenas_propriedades: bool = True,
    filtro_variedade: Optional[str] = None,
    filtro_propriedade: Optional[str] = None
) -> Dict[str, Any]:
    """
    Lista as ROIs de um usuário com filtros, contagem total e paginação.
    Esta versão foi refatorada para construir a query dinâmica de forma segura.
    """
    try:
        where_clauses = ["user_id = $1", "tipo_roi = 'PROPRIEDADE'"]
        count_params = [user_id]
        data_params = [user_id]

        if filtro_propriedade:
            propriedade_filter_clause = f"nome_propriedade = ${len(data_params) + 1}"
            where_clauses.append(propriedade_filter_clause)
            count_params.append(filtro_propriedade)
            data_params.append(filtro_propriedade)

        if filtro_variedade:
            variedade_filter_clause = f"""
            EXISTS (
                SELECT 1 FROM regiao_de_interesse talhoes
                WHERE talhoes.roi_pai_id = regiao_de_interesse.roi_id
                AND talhoes.metadata->>'variedade' ILIKE ${len(data_params) + 1}
            )
            """
            where_clauses.append(variedade_filter_clause)
            filter_value = f"%{filtro_variedade}%"
            count_params.append(filter_value)
            data_params.append(filter_value)

        final_where_clause = " WHERE " + " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) FROM regiao_de_interesse{final_where_clause}"
        total_records = await conn.fetchval(count_query, *count_params)

        if total_records == 0:
            return {"total": 0, "rois": []}

        select_query = """
            SELECT roi_id, nome, descricao, tipo_origem, status,
                   data_criacao, data_modificacao, tipo_roi, roi_pai_id,
                   nome_propriedade, nome_talhao
            FROM regiao_de_interesse
        """

        pagination_clause = f" ORDER BY data_criacao DESC LIMIT ${len(data_params) + 1} OFFSET ${len(data_params) + 2}"
        data_params.extend([limit, offset])

        final_data_query = select_query + final_where_clause + pagination_clause

        results = await conn.fetch(final_data_query, *data_params)

        return {"total": total_records, "rois": [dict(row) for row in results]}

    except Exception as e:
        logger.error(f"Erro ao listar ROIs: {str(e)}", exc_info=True)
        raise


@with_db_connection
async def obter_roi_por_id(conn, roi_id: int, user_id: int) -> Optional[Dict]:
    """
    Obtém uma ROI específica verificando o proprietário
    """
    try:
        result = await conn.fetchrow(
            """
            SELECT roi_id, nome, descricao, ST_AsGeoJSON(geometria)::json as geometria,
                   tipo_origem, status, data_criacao, data_modificacao, metadata, tipo_roi, nome_propriedade
            FROM regiao_de_interesse
            WHERE roi_id = $1 AND user_id = $2
            """,
            roi_id, user_id
        )
        if not result:
            return None

        row_dict = dict(result)
        metadata = row_dict.get('metadata')
        
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        elif metadata is None:
            metadata = {}
            
        row_dict['metadata'] = metadata

        if row_dict.get('tipo_roi') == 'PROPRIEDADE' and 'feature_collection_talhoes' in metadata:
            row_dict['geometria'] = metadata['feature_collection_talhoes']

        return row_dict
    except Exception as e:
        logger.error(f"Erro ao obter ROI: {str(e)}", exc_info=True)
        raise


@with_db_connection
async def atualizar_roi(conn, roi_id: int, user_id: int, update_data: Dict) -> Optional[Dict]:
    """
    Atualiza os metadados de uma ROI
    """
    try:
        result = await conn.fetchrow(
            """
            UPDATE regiao_de_interesse
            SET nome = COALESCE($3, nome),
                descricao = COALESCE($4, descricao),
                status = COALESCE($5, status),
                data_modificacao = CURRENT_TIMESTAMP
            WHERE roi_id = $1 AND user_id = $2
            RETURNING roi_id, nome, descricao, status, data_modificacao
            """,
            roi_id,
            user_id,
            update_data.get('nome'),
            update_data.get('descricao'),
            update_data.get('status')
        )
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Erro ao atualizar ROI: {str(e)}", exc_info=True)
        raise


@with_db_connection
async def deletar_roi(conn, roi_id: int, user_id: int) -> bool:
    """
    Remove uma ROI do banco de dados
    """
    try:
        result = await conn.execute(
            "DELETE FROM regiao_de_interesse WHERE roi_id = $1 AND user_id = $2",
            roi_id, user_id
        )
        return result == "DELETE 1"
    except Exception as e:
        logger.error(f"Erro ao deletar ROI: {str(e)}", exc_info=True)
        raise


@with_db_connection
async def listar_propriedades_unicas(conn, user_id: int) -> List[str]:
    """
    Busca e retorna uma lista de nomes de propriedades únicos para um usuário.
    """
    try:
        query = """
            SELECT DISTINCT nome_propriedade
            FROM regiao_de_interesse
            WHERE user_id = $1
              AND tipo_roi = 'PROPRIEDADE'
              AND nome_propriedade IS NOT NULL
              AND TRIM(nome_propriedade) <> ''
            ORDER BY nome_propriedade;
        """
        results = await conn.fetch(query, user_id)
        return [row['nome_propriedade'] for row in results]
    except Exception as e:
        logger.error(
            f"Erro ao listar propriedades únicas: {str(e)}", exc_info=True)
        raise


@with_db_connection
async def listar_variedades_unicas(conn, user_id: int) -> List[str]:
    """
    Busca e retorna uma lista de nomes de variedades únicos para um usuário,
    garantindo que o campo 'variedade' seja extraído corretamente dos metadados dos talhões.
    """
    try:
        query = """
            SELECT DISTINCT metadata->>'variedade' AS variedade
            FROM regiao_de_interesse
            WHERE user_id = $1
              AND tipo_roi = 'TALHAO'
              AND metadata ? 'variedade'
              AND metadata->>'variedade' IS NOT NULL
              AND TRIM(metadata->>'variedade') <> ''
            ORDER BY variedade;
        """
        results = await conn.fetch(query, user_id)

        variedades_encontradas = [row['variedade'] for row in results]
        logger.info(
            f"Variedades únicas encontradas no banco: {variedades_encontradas}")

        return variedades_encontradas
    except Exception as e:
        logger.error(
            f"Erro ao listar variedades únicas: {str(e)}", exc_info=True)
        raise


@with_db_connection
async def listar_talhoes_por_variedade(conn, user_id: int, variedade: str) -> List[Dict]:
    """
    Busca os dados (id, nome, geometria) de todos os talhões de um usuário 
    que correspondem a uma variedade específica.
    """
    query = """
        SELECT 
            roi_id, 
            nome_talhao, 
            ST_AsGeoJSON(geometria)::json as geometria
        FROM regiao_de_interesse
        WHERE user_id = $1
          AND tipo_roi = 'TALHAO'
          AND metadata->>'variedade' ILIKE $2;
    """
    results = await conn.fetch(query, user_id, f"%{variedade}%")

    return [dict(row) for row in results]


@with_db_connection
async def listar_talhoes_por_propriedade(conn, propriedade_id: int, user_id: int) -> List[Dict]:
    """
    Busca todas as ROIs do tipo 'TALHAO' associadas a uma ROI pai (propriedade).
    """
    query = """
        SELECT 
            roi_id, nome, descricao, 
            COALESCE(ST_AsGeoJSON(geometria)::json, '{}'::json) as geometria,
            tipo_origem, status, data_criacao, data_modificacao,
            tipo_roi, roi_pai_id, nome_propriedade, nome_talhao
        FROM regiao_de_interesse
        WHERE user_id = $1 AND roi_pai_id = $2 AND tipo_roi = 'TALHAO'
        ORDER BY nome_talhao;
    """
    results = await conn.fetch(query, user_id, propriedade_id)
    return [dict(row) for row in results]

@with_db_connection
async def listar_talhoes_por_propriedade_e_variedade(conn, user_id: int, propriedade_id: int, variedade: str) -> List[Dict]:
    """
    Busca os IDs de todos os talhões de um usuário que correspondem
    a uma propriedade e variedade específicas.
    """
    query = """
        SELECT roi_id, nome_talhao
        FROM regiao_de_interesse
        WHERE user_id = $1
          AND roi_pai_id = $2
          AND tipo_roi = 'TALHAO'
          AND metadata->>'variedade' ILIKE $3;
    """
    results = await conn.fetch(query, user_id, propriedade_id, f"%{variedade}%")
    return [dict(row) for row in results]

@with_db_connection
async def listar_rois_por_ids_para_batch(conn, roi_ids: List[int], user_id: int) -> List[Dict]:
    """
    Busca e retorna uma lista de ROIs a partir de uma lista de IDs,
    verificando a propriedade do usuário. Otimizado para processos em lote.
    """
    try:
        if not roi_ids:
            return []

        query = """
            SELECT
                roi_id, nome, ST_AsGeoJSON(geometria)::json as geometria, metadata,
                nome_propriedade, nome_talhao
            FROM regiao_de_interesse
            WHERE user_id = $1 AND roi_id = ANY($2::int[]);
        """
        rois = await conn.fetch(query, user_id, roi_ids)
        return [dict(row) for row in rois]
    except Exception as e:
        logger.error(f"Erro ao buscar ROIs em lote: {str(e)}", exc_info=True)
        raise
