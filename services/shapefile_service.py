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
from utils.normalization_utils import normalize_name

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
    Processador de shapefiles que converte para uma geometra 2D 
    cria uma estrutura hierárquica de ROIs (Propriedades e Talhões)
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
                logger.info(f"Shapefile lido com sucesso usando a codificação: '{encoding}'")
                break  # Se bem-sucedido, sai do loop
            except UnicodeDecodeError:
                logger.warning(f"Falha ao ler shapefile com a codificação '{encoding}'. Tentando a próxima.")
                continue
        
        # Se nenhuma codificação funcionou, lança um erro
        if gdf is None:
            raise ValueError(
                "Não foi possível ler o shapefile com as codificações testadas: "
                f"{', '.join(encodings_to_try)}. O arquivo .dbf pode estar corrompido ou em uma codificação inesperada."
            )

        if gdf.empty:
            raise ValueError("Shapefile não contém features")
            
        logger.info(f"Shapefile carregado com {len(gdf)} features, CRS: {gdf.crs}")
        return gdf

    async def _ensure_wgs84(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Garante que o GeoDataFrame esteja no sistema de coordenadas WGS84 (EPSG:4326)."""
        if gdf.crs is None:
            logger.warning("CRS não definido. Assumindo WGS84 (EPSG:4326).")
            gdf = gdf.set_crs("EPSG:4326", allow_override=True) # [cite: 120]
        elif gdf.crs.to_epsg() != 4326:
            logger.info(f"Convertendo CRS de {gdf.crs} para EPSG:4326.")
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
        
    async def process(self, temp_dir: Path, property_col: str, plot_col: str) -> List[Dict[str, Any]]:
        """
        Processa o shapefile, criando uma estrutura hierárquica de propriedades e talhões.

        Args:
            temp_dir: Diretório temporário com os arquivos do shapefile.
            property_col: Nome da coluna que identifica a Propriedade.
            plot_col: Nome da coluna que identifica o Talhão.

        Returns:
            Uma lista de dicionários, onde cada dicionário representa uma propriedade
            e contém uma lista de seus talhões.
        """
        try:
            gdf = await self._read_shapefile(temp_dir)
            crs_original = str(gdf.crs) if gdf.crs else "Não definido"
            
            gdf = await self._ensure_wgs84(gdf)
            gdf['geometry'] = gdf['geometry'].apply(convert_3d_to_2d)
            logger.info("Geometrias 3D convertidas para 2D.")
    
            if property_col not in gdf.columns:
                raise ValueError(f"A coluna de propriedade '{property_col}' não foi encontrada. Colunas disponíveis: {list(gdf.columns)}")
            if plot_col not in gdf.columns:
                raise ValueError(f"A coluna de talhão '{plot_col}' não foi encontrada. Colunas disponíveis: {list(gdf.columns)}")
    
            date_columns = gdf.select_dtypes(include=['datetime', 'datetimetz']).columns
            if not date_columns.empty:
                for col in date_columns:
                    gdf[col] = gdf[col].apply(lambda x: x.isoformat() if pd.notnull(x) else None)
    
            normalized_col_name = "normalized_property_name"
            gdf[normalized_col_name] = gdf[property_col].apply(lambda x: normalize_name(str(x), case='title'))
            
            results = []
            grouped_by_property = gdf.groupby(normalized_col_name)
            
            for normalized_name, group_gdf in grouped_by_property:
                if group_gdf.empty:
                    continue
                
                property_geometry = unary_union(group_gdf['geometry'])
                original_property_name = group_gdf[property_col].iloc[0]
                
                area_m2 = gpd.GeoSeries([property_geometry], crs="EPSG:4326").to_crs(epsg=3857).area.sum()
                area_ha = area_m2 / 10000
                
                property_data = {
                    "nome_propriedade": str(normalized_name),
                    "geometria": mapping(property_geometry),
                    "metadata": {
                        "total_features": len(group_gdf),
                        "area_total_ha": round(area_ha, 4),
                        "bbox": [float(b) for b in property_geometry.bounds],
                        "crs_original": crs_original,
                        "sistema_referencia": "EPSG:4326",
                        "nome_original_propriedade": original_property_name
                    },
                    "talhoes": []
                }
    
                for _, talhao_row in group_gdf.iterrows():
                    talhao_geometry = talhao_row['geometry']
                    
                    # --- INÍCIO DA CORREÇÃO ---
                    
                    # Limpa os atributos e PADRONIZA AS CHAVES PARA MINÚSCULAS
                    raw_attributes = talhao_row.drop(['geometry', normalized_col_name]).to_dict()
                    cleaned_attributes = {}
                    for key, value in raw_attributes.items():
                        clean_key = str(key).lower()  # Converte a chave para minúsculas
                        if pd.isna(value):
                            cleaned_attributes[clean_key] = None
                        else:
                            cleaned_attributes[clean_key] = value
    
                    # Calcula e adiciona a área individual do talhão
                    talhao_series_m2 = gpd.GeoSeries([talhao_geometry], crs="EPSG:4326").to_crs(epsg=3857).area
                    talhao_area_ha = (talhao_series_m2.iloc[0] / 10000) if not talhao_series_m2.empty else 0
                    cleaned_attributes['area_ha'] = round(talhao_area_ha, 4)
    
                    # --- FIM DA CORREÇÃO ---
    
                    talhao_data = {
                        "nome_talhao": str(talhao_row[plot_col]),
                        "geometria": mapping(talhao_geometry),
                        "metadata": cleaned_attributes
                    }
                    property_data["talhoes"].append(talhao_data)
                
                results.append(property_data)
                logger.info(f"Processada propriedade '{normalized_name}' com {len(property_data['talhoes'])} talhões.")
    
            if not results:
                raise ValueError("Nenhum grupo de propriedade válido foi processado a partir do shapefile.")
    
            return results
    
        except Exception as e:
            logger.error(f"Erro no processamento hierárquico do shapefile: {str(e)}", exc_info=True)
            raise
    