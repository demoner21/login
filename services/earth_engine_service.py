import ee
import logging
from typing import Dict, Any
from datetime import date

from services.earth_engine_initializer import initialize_earth_engine

logger = logging.getLogger(__name__)

# Inicializa o GEE ao carregar o módulo.
# Isso garante que a inicialização ocorra apenas uma vez.
try:
    initialize_earth_engine()
except Exception as e:
    logger.error(f"Falha crítica ao inicializar o Earth Engine: {e}")

class EarthEngineService:
    """
    Serviço para processar e exportar imagens do Google Earth Engine.
    """

    def get_download_url(
        self,
        geometry: Dict[str, Any],
        start_date: date,
        end_date: date,
        scale: int = 10
    ) -> str:
        """
        Gera um link de download para uma imagem de satélite (Sentinel-2)
        processada para uma determinada geometria e período.

        Args:
            geometry: Dicionário GeoJSON da geometria para o recorte.
            start_date: Data de início do período de busca.
            end_date: Data de fim do período de busca.
            scale: Resolução da imagem em metros (padrão: 10m para Sentinel-2).

        Returns:
            URL para download da imagem em formato GeoTIFF.
        """
        try:
            # 1. Converte a geometria do GeoJSON para um objeto do Earth Engine
            roi_ee = ee.Geometry(geometry)

            # 2. Seleciona a coleção de imagens (Sentinel-2 Nível 2A - Reflectância de Superfície)
            collection = (
                ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(roi_ee)
                .filterDate(ee.Date(start_date.isoformat()), ee.Date(end_date.isoformat()))
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            )

            # 3. Pega a imagem mais recente (ou cria um mosaico) e aplica o recorte
            image = ee.Image(collection.mosaic()).clip(roi_ee)

            # 4. Define os parâmetros de visualização (bandas RGB) e gera a URL de download
            download_params = {
                'bands': ['B4', 'B3', 'B2'], # RGB
                'min': 0,
                'max': 3000, # Valores de reflectância típicos para escalar para visualização
                'scale': scale,
                'format': 'GEO_TIFF' # Exporta como GeoTIFF
            }
            
            url = image.getDownloadURL(download_params)
            logger.info(f"URL de download do GEE gerada com sucesso.")
            return url

        except Exception as e:
            logger.error(f"Erro ao processar imagem no Earth Engine: {e}", exc_info=True)
            # Em um cenário real, você pode querer lançar uma exceção mais específica
            raise ValueError(f"Não foi possível gerar a imagem do GEE. Detalhe: {str(e)}")

# Instância única do serviço para ser usada em toda a aplicação
gee_service = EarthEngineService()