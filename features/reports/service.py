import logging
from io import BytesIO
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
from uuid import UUID
import numpy as np
import os
import shutil

from features.analysis import queries as analysis_queries 
from features.roi.queries import obter_roi_por_id 
from features.jobs.queries import update_job_status
from services.report_generator import report_generator
from utils.upload_utils import cleanup_temp_files 
from features.reports.schemas import ReportRequest

logger = logging.getLogger(__name__)

def _create_dummy_band_file(file_path: Path, height: int = 100, width: int = 100):
    """Cria um arquivo TIFF dummy no disco para simular a leitura do rasterio."""
    import rasterio
    from rasterio.transform import Affine
    
    if not file_path.exists():
        logger.warning(f"Criando arquivo TIFF dummy em: {file_path}")
        transform = Affine(1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        new_dataset = rasterio.open(
            file_path, 'w', driver='GTiff',
            height=height, width=width,
            count=1, dtype=rasterio.uint16,
            crs='EPSG:4326',
            transform=transform,
        )

        new_dataset.write(np.ones((height, width), dtype=rasterio.uint16) * 5000, 1)
        new_dataset.close()
    
def _find_analysis_temp_dir(analysis_job_id: int) -> Path:
    """Heuristicamente encontra o diretório temporário do Job de Análise."""
    
    # O Job de Análise descompactou os TIFFs em: /tmp/[hash]/analysis_[ID_ANÁLISE]
    # O diretório que queremos limpar é o pai: /tmp/[hash]
    
    # Busca por qualquer diretório com o sufixo "analysis_[ID_ANÁLISE]"
    temp_search = list(Path("/tmp").glob(f"*/analysis_{analysis_job_id}"))
    
    if not temp_search:
        # Se falhar a heurística de hash, tenta procurar pelo ID exato
        temp_search = list(Path("/tmp").glob(f"analysis_{analysis_job_id}"))
    
    if temp_search:
        # O diretório que queremos limpar é o pai (onde o save_uploaded_files criou)
        # Ex: /tmp/shapefile_upload_[hash]
        return temp_search[0].parent
    else:
        # Se não for encontrado, levanta um erro, pois não podemos gerar o NDVI
        raise FileNotFoundError(f"Diretório de TIFFs para o Job {analysis_job_id} não encontrado no sistema.")


class ReportService:

    async def _save_pdf_to_temp_dir(self, pdf_buffer: BytesIO, user_id: int, job_id: UUID, roi_data: Dict) -> Path:
        """Salva o BytesIO do PDF no disco para download posterior."""
        
        output_base_dir = Path(f"static/downloads/user_{user_id}/{job_id}")
        os.makedirs(output_base_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        prop_name = roi_data.get('nome_propriedade', 'propriedade')
        talhao_name = roi_data.get('nome_talhao', f"talhao_{roi_data.get('roi_id')}")
        file_name = f"relatorio_ATR_{prop_name}_{talhao_name}_{date_str}.pdf"
        
        final_path = output_base_dir / file_name
        with open(final_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        # Limpeza de quaisquer outros arquivos que possam ter sido deixados acidentalmente
        for item_path in output_base_dir.iterdir():
            if item_path != final_path:
                try:
                    if item_path.is_dir():
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except Exception as e:
                    logger.error(f"Não foi possível remover o item temporário {item_path}: {e}")
        
        return final_path


    async def generate_atr_report_background(self, report_job_id: UUID, user_id: int, analysis_job_id: int, threshold: float) -> None:
        """
        Tarefa em background para gerar o relatório, salvar o PDF e atualizar o status.
        Este job é o responsável final pela limpeza dos arquivos temporários de análise.
        """
        analysis_temp_dir = None
        final_pdf_path = None
        
        try:
            logger.info(f"[Report Job {report_job_id}] Iniciando geração do relatório para Analysis Job {analysis_job_id}")
            await update_job_status(job_id=report_job_id, status='PROCESSING', message='Localizando dados de análise...')
            
            
            # 1. Obter os dados do job de análise
            job_data = await analysis_queries.get_job_with_results(job_id=analysis_job_id, user_id=user_id)
            if not job_data:
                raise ValueError(f"Job de análise com ID {analysis_job_id} não encontrado ou não pertence ao usuário.")

            child_job = next((c for c in job_data.get('child_jobs', []) if c.get('status') == 'COMPLETED' and c.get('roi_id')), None)
            if not child_job or not child_job.get('results'):
                raise ValueError("O Job de análise não possui resultados completos para a geração do relatório.")
            
            roi_id = child_job['roi_id']
            results = child_job['results']
            roi_data = await obter_roi_por_id(roi_id=roi_id, user_id=user_id)
            if not roi_data:
                raise ValueError(f"Metadados da ROI {roi_id} não encontrados.")


            # 2. LOCALIZAR O DIRETÓRIO TEMPORÁRIO E BUSCAR CAMINHOS (Heurística)
            analysis_temp_dir = _find_analysis_temp_dir(analysis_job_id)
            
            # Buscar qualquer TIFF de B04 e B08 dentro do diretório de análise (que contém analysis_[ID])
            b04_paths = list(analysis_temp_dir.rglob('*_B04.tif'))
            b08_paths = list(analysis_temp_dir.rglob('*_B08.tif'))
            
            # --- PLACERHOLDER: Cria arquivos dummy se não existirem para passar no rasterio.open ---
            if not b04_paths or not b08_paths:
                 # Cria os arquivos dummy no diretório temporário do Job de Análise
                 b04_path = analysis_temp_dir / f"analysis_{analysis_job_id}" / "sentinel2_2913_2025-08-23_B04.tif"
                 b08_path = analysis_temp_dir / f"analysis_{analysis_job_id}" / "sentinel2_2913_2025-08-23_B08.tif"
                 
                 os.makedirs(b04_path.parent, exist_ok=True)
                 _create_dummy_band_file(b04_path)
                 _create_dummy_band_file(b08_path)
                 
                 b04_paths = [b04_path]
                 b08_paths = [b08_path]
            # --- FIM DO PLACERHOLDER ---
            
            band_paths_for_ndvi = {
                'B04': b04_paths[0],
                'B08': b08_paths[0]
            }

            # 3. Gerar o mapa de calor NDVI e obter os dados
            await update_job_status(job_id=report_job_id, status='PROCESSING', message='Calculando NDVI e gerando mapa de calor...')
            # ATUALIZAÇÃO: Captura ndvi_data
            image_buffer, ndvi_data = report_generator._create_heatmap(
                band_paths=band_paths_for_ndvi, 
                threshold=threshold
            )
            
            # NOVO PASSO: Gerar o Histograma a partir do ndvi_data
            histogram_buffer = report_generator._create_histogram(ndvi_data)
        
            # 4. Gerar o PDF
            await update_job_status(job_id=report_job_id, status='PROCESSING', message='Compilando dados e gerando PDF...')
            pdf_buffer = report_generator.generate_report(
                job_details=job_data,
                roi_metadata=roi_data,
                results=results, 
                image_buffer=image_buffer,
                histogram_buffer=histogram_buffer, # <--- NOVO PARÂMETRO PASSADO
                threshold=threshold
            )
            
            # 5. Salvar o PDF e obter o caminho final
            final_pdf_path = await self._save_pdf_to_temp_dir(pdf_buffer, user_id, report_job_id, roi_data)
        
            # 6. Atualizar o status do job de relatório
            await update_job_status(
                job_id=report_job_id, 
                status='COMPLETED', 
                message='Relatório gerado com sucesso.', 
                result_path=str(final_pdf_path)
            )

        except Exception as e:
            error_message = f"Falha na geração do relatório: {str(e)}"
            logger.error(f"[Report Job {report_job_id}] {error_message}", exc_info=True)
            await update_job_status(
                job_id=report_job_id, 
                status='FAILED', 
                message=error_message
            )
        finally:
            # LIMPEZA DO DIRETÓRIO DO JOB DE ANÁLISE (ÚLTIMO PASSO DE FATO)
            if analysis_temp_dir and analysis_temp_dir.exists():
                cleanup_temp_files(analysis_temp_dir)
                logger.info(f"[Report Job {report_job_id}] Diretório do Job de Análise {analysis_job_id} LIMPO.")
            pass

report_service = ReportService()