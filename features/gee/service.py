import ee
import os
import logging
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from shapely.geometry import shape, mapping, Polygon, MultiPolygon

from services.earth_engine_initializer import initialize_earth_engine
from utils.text_normalizer import normalize_name

logger = logging.getLogger(__name__)

_gee_initialized = False

def _ensure_gee_initialized():
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

    async def _download_band_async(self, session: aiohttp.ClientSession, image: ee.Image, band: str, region: Dict, filename: Path, scale: int = 10, crs: str = 'EPSG:4326') -> Optional[str]:
        """
        Baixa uma única banda de forma assíncrona usando a URL de download do GEE.
        """
        try:
            single_band_image = image.select(band)
            logger.info(f"Preparando download para banda {band} em {filename.name}")
            
            download_url = single_band_image.getDownloadURL({
                'scale': scale,
                'region': region,
                'format': 'GEO_TIFF',
                'crs': crs
            })

            async with session.get(download_url) as response:
                if response.status == 200:
                    async with aiofiles.open(filename, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024)
                            if not chunk:
                                break
                            await f.write(chunk)
                    logger.info(f"Banda {band} baixada com sucesso: {filename.name}")
                    return str(filename)
                else:
                    error_text = await response.text()
                    logger.error(f"Falha ao baixar a banda {band}. Status: {response.status}. Resposta: {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Erro excepcional ao baixar a banda {band}: {e}", exc_info=True)
            return None

    async def download_images_for_roi(
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
            bands = bands_to_download if bands_to_download and isinstance(bands_to_download, list) and bands_to_download else ALL_SENTINEL_BANDS

            prop_dir = output_base_dir / normalize_name(nome_propriedade, case='lower').replace(" ", "_")
            talhao_dir = prop_dir / normalize_name(nome_talhao, case='lower').replace(" ", "_")
            os.makedirs(talhao_dir, exist_ok=True)

            ee_geom = self._geometry_to_ee(roi['geometria'])

            collection = (
                ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(ee_geom)
                .filterDate(start_date, end_date)
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud_percentage))
            )

            image_list = collection.toList(collection.size())
            num_images = image_list.size().getInfo()

            if num_images == 0:
                results.update({"status": "warning", "message": "Nenhuma imagem encontrada."})
                return results

            logger.info(f"Encontradas {num_images} imagens para a ROI {roi_id}.")
            total_files_downloaded = 0
            
            async with aiohttp.ClientSession() as session:
                for i in range(num_images):
                    image = ee.Image(image_list.get(i))
                    date_millis = image.get('system:time_start').getInfo()
                    date_str = datetime.fromtimestamp(date_millis/1000).strftime('%Y-%m-%d')
                    date_dir = talhao_dir / date_str
                    os.makedirs(date_dir, exist_ok=True)

                    ee_region = ee_geom.bounds().getInfo()['coordinates']

                    tasks = []
                    for band_name in bands:
                        filename = date_dir / f"sentinel2_{roi_id}_{date_str}_{band_name}.tif"
                        if not os.path.exists(filename):
                            tasks.append(self._download_band_async(session, image, band_name, ee_region, filename, scale))

                    if tasks:
                        logger.info(f"Iniciando download concorrente de {len(tasks)} bandas para a data {date_str}...")
                        download_results = await asyncio.gather(*tasks)
                        successful_downloads = [res for res in download_results if res]
                        total_files_downloaded += len(successful_downloads)

            results.update({
                "status": "success",
                "message": f"{total_files_downloaded} arquivos de banda baixados para {num_images} datas.",
                "path": str(talhao_dir)
            })
            return results

        except Exception as e:
            logger.error(f"Erro no processamento de download para ROI {roi.get('roi_id')}: {e}", exc_info=True)
            results["message"] = str(e)
            return results


gee_service = EarthEngineService()