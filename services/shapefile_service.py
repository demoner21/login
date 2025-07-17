import logging
import os
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.ops import unary_union
from typing import Dict, List, Any
from pathlib import Path
import json
import pandas as pd
from datetime import date
from utils.text_normalizer import normalize_name
from collections import defaultdict
import fiona
from shapely.geometry import shape

logger = logging.getLogger(__name__)


def convert_3d_to_2d(geom):
    """Remove a dimensão Z de uma geometria, essencial para o GEE."""
    if geom is None or not geom.has_z:
        return geom

    if isinstance(geom, Polygon):
        exterior_2d = [(x, y) for x, y, *_ in geom.exterior.coords]
        interiors_2d = [[(x, y) for x, y, *_ in interior.coords]
                        for interior in geom.interiors]
        return Polygon(exterior_2d, interiors_2d)
    elif isinstance(geom, MultiPolygon):
        polygons_2d = [convert_3d_to_2d(poly) for poly in geom.geoms]
        return MultiPolygon(polygons_2d)
    return geom


class ShapefileSplitterProcessor:
    """
    Processador de shapefiles que converte para uma geometria 2D
    e cria uma estrutura hierárquica de ROIs (Propriedades e Talhões)
    a partir de colunas especificadas.
    """

    async def _read_shapefile(self, temp_dir: Path) -> gpd.GeoDataFrame:
        """Lê o arquivo .shp de um diretório temporário."""
        shp_files = list(temp_dir.glob("*.shp"))
        if not shp_files:
            raise ValueError("Nenhum arquivo .shp encontrado no diretório")

        # Lista de codificações comuns para tentar
        encodings_to_try = ['utf-8', 'latin-1', 'cp1252']
        gdf = None

        for encoding in encodings_to_try:
            try:
                gdf = gpd.read_file(shp_files[0], encoding=encoding)
                logger.info(
                    f"Shapefile lido com sucesso usando a codificação: '{encoding}'")
                break  # Se bem-sucedido, sai do loop
            except UnicodeDecodeError:
                logger.warning(
                    f"Falha ao ler shapefile com a codificação '{encoding}'. Tentando a próxima.")
                continue

        # Se nenhuma codificação funcionou, lança um erro
        if gdf is None:
            raise ValueError(
                "Não foi possível ler o shapefile com as codificações testadas: "
                f"{', '.join(encodings_to_try)}. O arquivo .dbf pode estar corrompido ou em uma codificação inesperada."
            )

        if gdf.empty:
            raise ValueError("Shapefile não contém features")

        logger.info(
            f"Shapefile carregado com {len(gdf)} features, CRS: {gdf.crs}")
        return gdf

    async def _ensure_wgs84(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Garante que o GeoDataFrame esteja no sistema de coordenadas WGS84 (EPSG:4326)."""
        if gdf.crs is None:
            logger.warning("CRS não definido. Assumindo WGS84 (EPSG:4326).")
            gdf = gdf.set_crs("EPSG:4326", allow_override=True)
        elif gdf.crs.to_epsg() != 4326:
            logger.info(f"Convertendo CRS de {gdf.crs} para EPSG:4326.")
            gdf = gdf.to_crs("EPSG:4326")
        return gdf

    async def process(self, temp_dir: Path, property_col: str, plot_col: str) -> List[Dict[str, Any]]:
        """
        Processa o shapefile em modo streaming para economizar memória,
        criando uma estrutura hierárquica de propriedades e talhões.
        """
        shp_files = list(temp_dir.glob("*.shp"))
        if not shp_files:
            raise ValueError("Nenhum arquivo .shp encontrado no diretório")

        shp_path = shp_files[0]

        properties_data = defaultdict(
            lambda: {"talhoes": [], "geometries": []})
        crs_original = "Não definido"

        # 1. Leitura em Streaming com Fiona para manter o uso de memória baixo
        try:
            with fiona.open(shp_path, 'r', encoding='utf-8') as source:
                crs_original = str(
                    source.crs) if source.crs else "Não definido"

                for feature in source:
                    geom = feature.get('geometry')
                    if geom is None:
                        continue

                    shapely_geom = shape(geom)
                    geom_2d = convert_3d_to_2d(shapely_geom)

                    prop_name = feature['properties'].get(property_col)
                    if prop_name is None:
                        continue

                    normalized_name = normalize_name(
                        str(prop_name), case='title')

                    properties_data[normalized_name]["talhoes"].append(
                        feature['properties'])
                    properties_data[normalized_name]["geometries"].append(
                        geom_2d)
        except Exception as e:
            logger.error(f"Falha ao ler o shapefile em modo streaming: {e}")
            raise ValueError(
                "Não foi possível ler o arquivo shapefile. Verifique o formato e a codificação."
            )

        if not properties_data:
            raise ValueError(
                "Nenhum grupo de propriedade válido foi processado."
            )

        # 2. Pós-processamento dos dados que agora estão em memória
        results = []
        try:
            for normalized_name, data in properties_data.items():
                property_geometry = unary_union(data['geometries'])

                temp_prop_gdf = gpd.GeoDataFrame(
                    [{'geometry': property_geometry}], crs="EPSG:4326")
                area_m2 = temp_prop_gdf.to_crs(epsg=3857).area.sum()
                area_ha = area_m2 / 10000
                final_area_ha = round(area_ha, 4) if pd.notna(area_ha) else None

                property_entry = {
                    "nome_propriedade": str(normalized_name),
                    "geometria": mapping(property_geometry),
                    "metadata": {
                        "total_features": len(data['talhoes']),
                        "area_total_ha": final_area_ha,
                        "bbox": [float(b) for b in property_geometry.bounds],
                        "crs_original": crs_original,
                        "sistema_referencia": "EPSG:4326",
                        "nome_original_propriedade": data['talhoes'][0].get(property_col, "")
                    },
                    "talhoes": []
                }

                for i, talhao_props in enumerate(data['talhoes']):
                    talhao_geometry = data['geometries'][i]

                    temp_talhao_gdf = gpd.GeoDataFrame(
                        [{'geometry': talhao_geometry}], crs="EPSG:4326")
                    talhao_area_m2 = temp_talhao_gdf.to_crs(epsg=3857).area.iloc[0]
                    talhao_area_ha = talhao_area_m2 / 10000
                    final_talhao_area_ha = round(
                        talhao_area_ha, 4) if pd.notna(talhao_area_ha) else None

                    cleaned_attributes = {
                        str(key).lower(): value if pd.notna(value) else None
                        for key, value in talhao_props.items()
                    }
                    cleaned_attributes['area_ha'] = final_talhao_area_ha

                    property_entry["talhoes"].append({
                        "nome_talhao": str(talhao_props.get(plot_col)),
                        "geometria": mapping(talhao_geometry),
                        "metadata": cleaned_attributes
                    })

                results.append(property_entry)
                logger.info(
                    f"Processada propriedade '{normalized_name}' com {len(property_entry['talhoes'])} talhões."
                )

            return results

        except Exception as e:
            logger.error(
                f"Erro no processamento hierárquico do shapefile: {str(e)}", exc_info=True)
            raise
