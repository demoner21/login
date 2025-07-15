import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
import re
from collections import defaultdict
from typing import List

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, UploadFile, status)

from features.auth.dependencies import get_current_user
from features.roi.queries import listar_rois_por_ids_para_batch

from services.shapefile_service import convert_3d_to_2d
from utils.upload_utils import cleanup_temp_files, save_uploaded_files
from . import queries, schemas
from .service import analysis_service

logger = logging.getLogger(__name__)
router = APIRouter()

async def run_multi_roi_analysis_in_background(parent_job_id: int, zip_path: Path, user_id: int):
    """
    Função em background que processa um .zip contendo imagens de múltiplos talhões.
    """
    analysis_dir = zip_path.parent / f"analysis_{parent_job_id}"
    
    try:
        logger.info(f"[Job Pai {parent_job_id}] Iniciando tarefa de análise em lote.")
        await queries.update_job_status(job_id=parent_job_id, status="PROCESSING")

        analysis_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(analysis_dir)
        logger.info(f"[Job Pai {parent_job_id}] Arquivo descompactado em: {analysis_dir}")

        # Padrão de arquivo que inclui o roi_id
        file_pattern = re.compile(r'sentinel2_(\d+)_(\d{4}-\d{2}-\d{2})_(B\d+A?)\.tif$')
        
        # Estrutura para agrupar arquivos por ROI e depois por data
        files_by_roi_and_date = defaultdict(lambda: defaultdict(dict))
        
        for tif_path in analysis_dir.rglob('*.tif'):
            match = file_pattern.search(tif_path.name)
            if match:
                roi_id_str, date_str, band_name = match.groups()
                files_by_roi_and_date[int(roi_id_str)][date_str][band_name] = tif_path
        
        if not files_by_roi_and_date:
            raise FileNotFoundError("Nenhum arquivo .tif com nome padronizado (sentinel2_{roi_id}_{data}_{banda}.tif) foi encontrado no ZIP.")

        # Buscar metadados de todas as ROIs encontradas de uma vez
        all_roi_ids = list(files_by_roi_and_date.keys())
        rois_data = await listar_rois_por_ids_para_batch(roi_ids=all_roi_ids, user_id=user_id)
        rois_metadata_map = {roi['roi_id']: roi for roi in rois_data}

        # Processar cada ROI encontrada no ZIP
        for roi_id, files_by_date in files_by_roi_and_date.items():
            child_job_id = await queries.create_analysis_job(user_id=user_id, roi_id=roi_id, parent_job_id=parent_job_id)
            
            try:
                roi_meta = rois_metadata_map.get(roi_id)
                if not roi_meta:
                    raise ValueError(f"Metadados da ROI {roi_id} não encontrados ou não pertencem ao usuário.")
                
                # Extrai a área em hectares
                metadata = roi_meta.get('metadata', {})
                hectares = metadata.get('area_ha')
                if hectares is None:
                     raise ValueError(f"Não foi possível encontrar a área ('area_ha') nos metadados da ROI {roi_id}")

                results_to_save = []
                for date_str, band_paths_dict in files_by_date.items():
                    logger.info(f"[Job Filho {child_job_id}] Processando data: {date_str} para ROI {roi_id}")
                    analysis_result = analysis_service.run_analysis_pipeline(
                        band_paths=band_paths_dict,
                        hectares=hectares
                    )
                    if analysis_result["status"] == "success":
                        results_to_save.append({
                            "date_analyzed": datetime.strptime(date_str, "%Y-%m-%d").date(),
                            "predicted_atr": analysis_result["predicted_atr"]
                        })

                if results_to_save:
                    await queries.save_analysis_results(job_id=child_job_id, results=results_to_save)
                
                await queries.update_job_status(job_id=child_job_id, status="COMPLETED")
                logger.info(f"[Job Filho {child_job_id}] Análise para ROI {roi_id} concluída com sucesso.")

            except Exception as e:
                logger.error(f"[Job Filho {child_job_id}] Erro na análise da ROI {roi_id}: {e}", exc_info=True)
                await queries.update_job_status(job_id=child_job_id, status="FAILED", error_message=str(e))
        
        await queries.update_job_status(job_id=parent_job_id, status="COMPLETED")

    except Exception as e:
        logger.error(f"[Job Pai {parent_job_id}] Erro na tarefa de background: {e}", exc_info=True)
        await queries.update_job_status(job_id=parent_job_id, status="FAILED", error_message=str(e))
    finally:
        cleanup_temp_files(zip_path.parent)
        logger.info(f"[Job Pai {parent_job_id}] Limpeza dos arquivos temporários concluída.")


@router.post(
    "/upload-analysis",
    response_model=schemas.AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Análise] Faz upload de imagens para análise em lote"
)
async def upload_for_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Arquivo .zip contendo imagens de um ou mais talhões."),
    current_user: dict = Depends(get_current_user)
):
    """
    Recebe um pacote de imagens .zip, inicia um job de análise em lote
    em background e retorna o ID do job "pai" para consulta futura.
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="O arquivo deve ser no formato .zip")

    try:
        temp_zip_path = save_uploaded_files([file])

        # Cria o job "pai" no banco de dados, sem roi_id
        parent_job_id = await queries.create_analysis_job(user_id=current_user['id'], roi_id=None)

        background_tasks.add_task(
            run_multi_roi_analysis_in_background,
            parent_job_id=parent_job_id,
            zip_path=temp_zip_path / file.filename,
            user_id=current_user['id']
        )
        
        return {
            "job_id": parent_job_id,
            "message": "O job de análise em lote foi criado e está na fila para processamento."
        }
    except Exception as e:
        logger.error(f"Erro ao iniciar o job de upload para análise em lote: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Não foi possível iniciar o job de análise.")

@router.get(
    "/jobs/{job_id}",
    response_model=schemas.AnalysisJobStatusResponse,
    summary="[Análise] Consulta o status de um job"
)
async def get_analysis_job_status(job_id: int, current_user: dict = Depends(get_current_user)):
    """
    Consulta o status e os resultados de um job de análise específico.
    """
    job = await queries.get_job_with_results(job_id=job_id, user_id=current_user['id'])
    if not job:
        raise HTTPException(status_code=404, detail=f"Job com ID {job_id} não encontrado ou não pertence ao usuário.")
    
    return job