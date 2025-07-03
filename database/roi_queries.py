import logging
from database.database import with_db_connection
from typing import List, Dict, Optional, Any
import json

logger = logging.getLogger(__name__)

def extract_geometry_from_geojson(geojson_data):
    """
    Extrai a geometria adequada do GeoJSON para armazenamento no PostGIS
    
    Args:
        geojson_data: Pode ser um dict ou string JSON contendo Feature, FeatureCollection, ou Geometry
        
    Returns:
        String JSON da geometria compatível com ST_GeomFromGeoJSON()
    """
    if isinstance(geojson_data, str):
        try:
            geojson_data = json.loads(geojson_data)
        except json.JSONDecodeError:
            raise ValueError("GeoJSON string inválido")
    
    if not isinstance(geojson_data, dict):
        raise ValueError("GeoJSON deve ser um dicionário ou string JSON válida")
    
    geom_type = geojson_data.get('type')
    
    if geom_type == 'FeatureCollection':
        features = geojson_data.get('features', [])
        if not features:
            raise ValueError("FeatureCollection não contém features")
            
        # Se há múltiplas features, criar uma GeometryCollection
        if len(features) == 1:
            # Uma única feature - extrair sua geometria
            geometry = features[0].get('geometry')
            if not geometry:
                raise ValueError("Feature não contém geometria")
            return json.dumps(geometry)
        else:
            # Múltiplas features - criar GeometryCollection
            geometries = []
            for feature in features:
                geom = feature.get('geometry')
                if geom:
                    geometries.append(geom)
            
            if not geometries:
                raise ValueError("Nenhuma geometria válida encontrada nas features")
            
            geometry_collection = {
                "type": "GeometryCollection",
                "geometries": geometries
            }
            return json.dumps(geometry_collection)
            
    elif geom_type == 'Feature':
        # Feature individual - extrair geometria
        geometry = geojson_data.get('geometry')
        if not geometry:
            raise ValueError("Feature não contém geometria")
        return json.dumps(geometry)
        
    elif geom_type in ['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon', 'GeometryCollection']:
        # Já é uma geometria
        return json.dumps(geojson_data)
        
    else:
        raise ValueError(f"Tipo de GeoJSON não suportado: {geom_type}")

@with_db_connection
async def criar_roi(
    conn,  # Conexão injetada pelo decorador
    *,  # Força os próximos argumentos a serem keyword-only
    user_id: int,
    roi_data: Dict
):
    """
    Cria uma nova ROI no banco de dados
    
    Args:
        conn: Conexão com o banco (injetada pelo decorador)
        user_id: ID do usuário proprietário
        roi_data: Dicionário com os dados da ROI
    """
    try:
        # Converte metadata para JSON string se for um dicionário
        metadata = roi_data.get('metadata', {})
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata)
            
        # Processa a geometria para garantir compatibilidade com PostGIS
        geometria_original = roi_data['geometria']
        geometria_para_postgis = extract_geometry_from_geojson(geometria_original)
        
        # Armazena a FeatureCollection original nos metadados se for o caso
        metadata_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
        
        # Se a geometria original era uma FeatureCollection, preservá-la nos metadados
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
    Cria uma ROI de Propriedade (pai) e várias ROIs de Talhão (filhas)
    dentro de uma única transação no banco de dados.
    """
    async with conn.transaction():
        # 1. Criar a ROI da Propriedade (Pai)
        prop_metadata = property_data.get('metadata', {})
        prop_metadata['nome_arquivo_original'] = shp_filename

        prop_insert_query = """
        INSERT INTO regiao_de_interesse 
        (user_id, nome, descricao, geometria, tipo_origem, metadata, sistema_referencia,
         nome_arquivo_original, tipo_roi, nome_propriedade)
        VALUES ($1, $2, $3, ST_GeomFromGeoJSON($4), $5, $6::jsonb, 'EPSG:4326', $7, 'PROPRIEDADE', $8)
        RETURNING roi_id, nome, ST_AsGeoJSON(geometria)::json as geometria, data_criacao;
        """
        
        prop_geom_json = json.dumps(property_data['geometria'])
        
        created_prop = await conn.fetchrow(
            prop_insert_query,
            user_id,
            property_data['nome'],
            property_data['descricao'],
            prop_geom_json,
            'shapefile_hierarchical',
            json.dumps(prop_metadata),
            shp_filename,
            property_data['nome_propriedade']
        )
        
        parent_roi_id = created_prop['roi_id']
        logger.info(f"ROI de Propriedade '{created_prop['nome']}' criada com ID: {parent_roi_id}")

        # 2. Criar as ROIs dos Talhões (Filhos/Filhas)
        created_plots = []
        plot_insert_query = """
        INSERT INTO regiao_de_interesse
        (user_id, nome, descricao, geometria, tipo_origem, metadata, sistema_referencia,
         nome_arquivo_original, tipo_roi, nome_propriedade, nome_talhao, roi_pai_id)
        VALUES ($1, $2, $3, ST_GeomFromGeoJSON($4), $5, $6::jsonb, 'EPSG:4326', $7, 'TALHAO', $8, $9, $10)
        RETURNING roi_id, nome, ST_AsGeoJSON(geometria)::json as geometria, data_criacao;
        """
        for plot in plots_data:
            plot_geom_json = json.dumps(plot['geometria'])
            created_plot = await conn.fetchrow(
                plot_insert_query,
                user_id,
                plot['nome'],
                plot['descricao'],
                plot_geom_json,
                'shapefile_hierarchical',
                json.dumps(plot.get('metadata', {})),
                shp_filename,
                property_data['nome_propriedade'],
                plot['nome_talhao'],
                parent_roi_id
            )
            created_plots.append(dict(created_plot))
        
        logger.info(f"{len(created_plots)} ROIs de Talhão criadas para a propriedade ID {parent_roi_id}.")

        return {"propriedade": dict(created_prop), "talhoes": created_plots}

@with_db_connection
async def listar_todas_rois_para_batch(conn) -> List[Dict]:
    """
    Lista todas as ROIs ativas do banco de dados para processamento em lote.
    Retorna apenas os campos essenciais: ID, nome e geometria.
    """
    try:
        results = await conn.fetch(
            """
            SELECT 
                roi_id, 
                nome, 
                ST_AsGeoJSON(geometria)::json as geometria
            FROM regiao_de_interesse
            WHERE status = 'ativo'
            ORDER BY roi_id
            """
        )
        # Processa a geometria para garantir que seja um dicionário
        processed_results = []
        for row in results:
            row_dict = dict(row)
            if isinstance(row_dict['geometria'], str):
                row_dict['geometria'] = json.loads(row_dict['geometria'])
            processed_results.append(row_dict)
        return processed_results
    except Exception as e:
        logger.error(f"Erro ao listar ROIs para batch: {str(e)}", exc_info=True)
        raise

@with_db_connection
async def listar_rois_usuario(conn, user_id: int, limit: int = 100, offset: int = 0, apenas_propriedades: bool = True) -> List[Dict]:
    """
    Lista as ROIs de um usuário. Por padrão, retorna apenas as propriedades (ROIs pai).
    
    Args:
        conn: Conexão com o banco de dados
        user_id: ID do usuário
        limit: Limite de resultados
        offset: Deslocamento
        apenas_propriedades: Se True, retorna apenas ROIs do tipo 'PROPRIEDADE'.
        
    Returns:
        Lista de dicionários com as ROIs do usuário
    """
    try:
        base_query = """
            SELECT 
                roi_id, nome, descricao, 
                COALESCE(ST_AsGeoJSON(geometria)::json, '{}'::json) as geometria,
                tipo_origem,
                status,
                data_criacao,
                data_modificacao,
                tipo_roi,
                roi_pai_id,
                nome_propriedade,
                nome_talhao
            FROM regiao_de_interesse
            WHERE user_id = $1
        """
        
        filter_condition = "AND tipo_roi = 'PROPRIEDADE'" if apenas_propriedades else ""
        
        query = f"{base_query} {filter_condition} ORDER BY data_criacao DESC LIMIT $2 OFFSET $3"
        
        results = await conn.fetch(query, user_id, limit, offset)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Erro ao listar ROIs: {str(e)}", exc_info=True)
        raise

@with_db_connection
async def obter_roi_por_id(conn, roi_id: int, user_id: int) -> Optional[Dict]:
    """
    Obtém uma ROI específica verificando o proprietário
    
    Args:
        conn: Conexão com o banco de dados
        roi_id: ID da ROI
        user_id: ID do usuário (para verificação de propriedade)
        
    Returns:
        Dicionário com os dados da ROI ou None se não encontrada
    """
    try:
        result = await conn.fetchrow(
            """
            SELECT roi_id, nome, descricao, ST_AsGeoJSON(geometria)::json as geometria,
                   tipo_origem, status, data_criacao, data_modificacao, metadata
            FROM regiao_de_interesse
            WHERE roi_id = $1 AND user_id = $2
            """,
            roi_id, user_id
        )
        
        if not result:
            return None
            
        row_dict = dict(result)
        
        # Se temos uma FeatureCollection original nos metadados, usar ela na resposta
        metadata = row_dict.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        
        if metadata and 'feature_collection_original' in metadata:
            row_dict['geometria'] = metadata['feature_collection_original']
            
        return row_dict
    except Exception as e:
        logger.error(f"Erro ao obter ROI: {str(e)}", exc_info=True)
        raise

@with_db_connection
async def atualizar_roi(conn, roi_id: int, user_id: int, update_data: Dict) -> Optional[Dict]:
    """
    Atualiza os metadados de uma ROI
    
    Args:
        conn: Conexão com o banco de dados
        roi_id: ID da ROI
        user_id: ID do usuário (para verificação)
        update_data: Dados para atualização:
            - nome: Novo nome (opcional)
            - descricao: Nova descrição (opcional)
            - status: Novo status (opcional)
            
    Returns:
        Dicionário com os dados atualizados ou None se não encontrada
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
    
    Args:
        conn: Conexão com o banco de dados
        roi_id: ID da ROI
        user_id: ID do usuário (para verificação)
        
    Returns:
        True se a ROI foi deletada, False caso contrário
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