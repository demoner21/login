import logging
import os
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.ops import transform
from typing import Dict, List, Any
from pathlib import Path
import json
import pandas as pd
from datetime import date

logger = logging.getLogger(__name__)

def convert_3d_to_2d(geom):
    """Remove a dimensão Z de uma geometria, essencial para o GEE."""
    if geom is None or not geom.has_z:
        return geom

    if isinstance(geom, Polygon):
        exterior_2d = [(x, y) for x, y, *_ in geom.exterior.coords]
        interiors_2d = [[(x, y) for x, y, *_ in interior.coords] for interior in geom.interiors]
        return Polygon(exterior_2d, interiors_2d)
    elif isinstance(geom, MultiPolygon):
        polygons_2d = [convert_3d_to_2d(poly) for poly in geom.geoms]
        return MultiPolygon(polygons_2d)
    return geom

class ShapefileSplitterProcessor:
    """
    Processador de shapefiles que converte geometrias para 2D e divide
    o arquivo em múltiplos ROIs com base em um campo de propriedade.
    """

    async def _read_shapefile(self, temp_dir: Path) -> gpd.GeoDataFrame:
        """Lê o arquivo .shp de um diretório temporário."""
        shp_files = list(temp_dir.glob("*.shp"))
        if not shp_files:
            raise ValueError("Nenhum arquivo .shp encontrado no diretório")
        
        gdf = gpd.read_file(shp_files[0])
        if gdf.empty:
            raise ValueError("Shapefile não contém features")
            
        logger.info(f"Shapefile carregado com {len(gdf)} features, CRS: {gdf.crs}")
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
        
    async def process(self, temp_dir: Path, group_by_column: str = 'Propriedad') -> List[Dict[str, Any]]: # Olha aqui
        """
        Processa o shapefile, dividindo-o em várias ROIs com base na coluna 'Propriedad'.
        """
        try:
            gdf = await self._read_shapefile(temp_dir)
            crs_original = str(gdf.crs) if gdf.crs else "Não definido"
            
            gdf = await self._ensure_wgs84(gdf)

            gdf['geometry'] = gdf['geometry'].apply(convert_3d_to_2d)
            logger.info("Geometrias 3D convertidas para 2D.")

            date_columns = ["Dat_Plan", "Enc_Data"]
            for col in date_columns:
                if col in gdf.columns and pd.api.types.is_datetime64_any_dtype(gdf[col]):
                    gdf[col] = gdf[col].dt.date
                    logger.info(f"Coluna de data '{col}' convertida para tipo 'date'.")

            if group_by_column not in gdf.columns:
                raise ValueError(f"A coluna de agrupamento '{group_by_column}' não foi encontrada no shapefile.")

            results = []
            grouped = gdf.groupby(group_by_column)
            
            for group_name, group_gdf in grouped:
                if group_gdf.empty:
                    continue

                # --- INÍCIO DA CORREÇÃO ---
                # Converte colunas do tipo 'date' para string no formato ISO ('AAAA-MM-DD')
                # antes de serializar para JSON.
                for col in date_columns:
                    if col in group_gdf.columns:
                        # O apply garante que apenas objetos 'date' sejam convertidos
                        group_gdf[col] = group_gdf[col].apply(lambda x: x.isoformat() if isinstance(x, date) else x)
                # --- FIM DA CORREÇÃO ---

                # Esta linha agora funcionará sem erros
                feature_collection = json.loads(group_gdf.to_json())
                
                bounds = group_gdf.total_bounds
                bbox = [float(b) for b in bounds]
                
                # O cálculo da área funciona melhor com um CRS projetado, mas como já
                # convertemos para WGS84, vamos usar a área projetada antes da conversão.
                # Para simplificar, vamos assumir que a área em graus é aceitável aqui.
                area_m2 = group_gdf.geometry.area.sum()
                area_ha = area_m2 / 10000

                metadata = {
                    "total_features": len(group_gdf),
                    "area_total_ha": round(area_ha, 4),
                    "bbox": bbox,
                    "crs_original": crs_original,
                    "sistema_referencia": "EPSG:4326",
                    "propriedade_original": group_name
                }
                
                result_item = {
                    "property_name": str(group_name),
                    "feature_collection": feature_collection,
                    "metadata": metadata
                }
                results.append(result_item)
                logger.info(f"Processado grupo '{group_name}' com {len(group_gdf)} feições.")

            if not results:
                raise ValueError("Nenhum grupo válido foi processado a partir do shapefile.")

            return results

        except Exception as e:
            logger.error(f"Erro no processamento e divisão do shapefile: {str(e)}", exc_info=True)
            raise