import ee
import geemap
import os
import time
import gc
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from shapely.geometry import shape, mapping, Polygon, MultiPolygon

from services.earth_engine_initializer import initialize_earth_engine
from utils.text_normalizer import normalize_name

logger = logging.getLogger(__name__)

# Flag global para controlar a inicialização e garantir que ocorra apenas uma vez.
_gee_initialized = False

def _ensure_gee_initialized():
    """
    Função interna que verifica a flag e inicializa o Earth Engine se necessário.
    Ela chama a sua função de inicialização que usa as credenciais da conta de serviço.
    """
    global _gee_initialized
    if not _gee_initialized:
        try:
            logger.info("Primeira requisição ao GEE. Tentando inicializar o Earth Engine...")
            initialize_earth_engine()
            _gee_initialized = True
            logger.info("Google Earth Engine inicializado com sucesso para esta sessão.")
        except Exception as e:
            logger.critical(f"FALHA CRÍTICA AO INICIALIZAR O EARTH ENGINE: {e}", exc_info=True)
            raise e


class EarthEngineService:
    """
    Serviço para processar e exportar imagens do Google Earth Engine.
    """

    def _convert_3d_to_2d(self, geom):
        """Remove a dimensão Z de uma geometria, se presente."""
        if geom is None or not geom.has_z:
            return geom
        
        if isinstance(geom, Polygon):
            exterior_2d = [(x, y) for x, y, *_ in geom.exterior.coords]
            interiors_2d = [[(x, y) for x, y, *_ in interior.coords] for interior in geom.interiors]
            return Polygon(exterior_2d, interiors_2d)
        elif isinstance(geom, MultiPolygon):
            polygons_2d = [self._convert_3d_to_2d(poly) for poly in geom.geoms]
            return MultiPolygon(polygons_2d)
        return geom

    def _geometry_to_ee(self, geometry_dict: Dict, max_vertices: int = 4000) -> ee.Geometry:
        """Converte uma geometria GeoJSON (dict) para um objeto ee.Geometry com simplificação."""
        try:
            geom = shape(geometry_dict)
            if not geom.is_valid:
                geom = geom.buffer(0)
            
            geom = self._convert_3d_to_2d(geom)

            if hasattr(geom, 'exterior') and len(geom.exterior.coords) > max_vertices:
                geom = geom.simplify(0.0001, preserve_topology=True)

            geojson_dict = mapping(geom)
            return ee.Geometry(geojson_dict)

        except Exception as e:
            logger.error(f"Erro ao converter geometria para EE: {e}")
            raise ValueError("Falha ao converter a geometria para o formato do Earth Engine.")

    def get_download_url(
        self,
        geometry: Dict[str, Any],
        start_date: date,
        end_date: date,
        scale: int = 10
    ) -> str:
        """
        Gera um link de download para uma imagem de satélite (Sentinel-2) processada.
        """
        _ensure_gee_initialized()
        try:
            roi_ee = ee.Geometry(geometry)

            collection = (
                ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(roi_ee)
                .filterDate(ee.Date(start_date.isoformat()), ee.Date(end_date.isoformat()))
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            )

            image = ee.Image(collection.mosaic()).clip(roi_ee)

            download_params = {
                'bands': ['B4', 'B3', 'B2'],
                'min': 0,
                'max': 3000,
                'scale': scale,
                'format': 'GEO_TIFF'
            }

            url = image.getDownloadURL(download_params)
            logger.info("URL de download do GEE gerada com sucesso.")
            return url

        except Exception as e:
            logger.error(f"Erro ao processar imagem no Earth Engine: {e}", exc_info=True)
            raise ValueError(f"Não foi possível gerar a imagem do GEE. Detalhe: {str(e)}")


    def download_images_for_roi(
        self,
        *,
        roi: Dict[str, Any],
        start_date: str,
        end_date: str,
        output_base_dir: Path,
        max_cloud_percentage: int = 5,
        scale: int = 10,
        bands_to_download: Optional[List[str]] = None
    ) -> Dict:
        """
        Baixa imagens do Sentinel-2 para uma única ROI, salvando um GeoTIFF multibanda por data.
        Se 'bands_to_download' não for fornecido, baixa todas as 12 bandas principais.
        """
        _ensure_gee_initialized()
        results = {"status": "failure", "message": "", "path": ""}
        try:
            roi_id = roi.get('roi_id')
            nome_propriedade = roi.get('nome_propriedade', 'propriedade_desconhecida')
            nome_talhao = roi.get('nome_talhao', f"talhao_{roi_id}")

            if not roi.get('geometria'):
                results["message"] = f"ROI {roi_id} não possui geometria."
                return results

            ALL_SENTINEL_BANDS = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B9', 'B11', 'B12']
            bands = bands_to_download if bands_to_download else ALL_SENTINEL_BANDS

            prop_dir = output_base_dir / normalize_name(nome_propriedade, case='lower').replace(" ", "_")
            talhao_dir = prop_dir / normalize_name(nome_talhao, case='lower').replace(" ", "_")
            os.makedirs(talhao_dir, exist_ok=True)

            ee_geom = self._geometry_to_ee(roi['geometria'])

            collection = (
                ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(ee_geom)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud_percentage))
                .select(bands)
            )

            image_list = collection.toList(collection.size())
            num_images = image_list.size().getInfo()

            if num_images == 0:
                results.update({"status": "warning", "message": "Nenhuma imagem encontrada para os filtros aplicados."})
                return results

            logger.info(f"Encontradas {num_images} imagens para a ROI {roi_id}.")
            downloaded_count = 0
            for i in range(num_images):
                image = ee.Image(image_list.get(i))
                date_millis = image.get('system:time_start').getInfo()
                date_str = datetime.fromtimestamp(date_millis/1000).strftime('%Y-%m-%d')

                date_dir = talhao_dir / date_str
                os.makedirs(date_dir, exist_ok=True)

                filename = date_dir / f"sentinel2_{roi_id}_{date_str}_multiband.tif"

                if os.path.exists(filename):
                    continue

                geemap.download_ee_image(
                    image.clip(ee_geom),
                    filename=str(filename),
                    scale=scale,
                    crs='EPSG:4326',
                    region=ee_geom.bounds()
                )
                downloaded_count += 1
                time.sleep(0.5)

            gc.collect()
            results.update({"status": "success", "message": f"{downloaded_count} imagens multibanda baixadas.", "path": str(talhao_dir)})
            return results

        except Exception as e:
            logger.error(f"Erro no download para ROI {roi.get('roi_id')}: {e}", exc_info=True)
            results["message"] = str(e)
            return results


gee_service = EarthEngineService()
