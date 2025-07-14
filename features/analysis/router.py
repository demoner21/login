import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
import re
from collections import defaultdict

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, UploadFile, status)

from features.auth.dependencies import get_current_user
from features.roi.queries import obter_roi_por_id
from services.shapefile_service import convert_3d_to_2d
from utils.upload_utils import cleanup_temp_files, save_uploaded_files
from . import queries, schemas
from .service import analysis_service

logger = logging.getLogger(__name__)
router = APIRouter()

async def run_analysis_in_background(job_id: int, zip_path: Path, roi_id: int, user_id: int):
    """
    Função em background que busca arquivos .tif, agora esperando nomes padronizados.
    """
    analysis_dir = zip_path.parent / f"analysis_{job_id}"
    results_to_save = []
    
    try:
        logger.info(f"[Job {job_id}] Iniciando tarefa em background.")
        await queries.update_job_status(job_id=job_id, status="PROCESSING")

        analysis_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(analysis_dir)
        logger.info(f"[Job {job_id}] Arquivo descompactado em: {analysis_dir}")

        roi_data = await obter_roi_por_id(roi_id=roi_id, user_id=user_id)
        if not roi_data:
             raise ValueError(f"ROI {roi_id} não encontrada para o usuário.")
        metadata = roi_data.get('metadata', {})
        if 'area_ha' in metadata:
            hectares = metadata['area_ha']
        elif 'area_total_ha' in metadata:
            hectares = metadata['area_total_ha']
        else:
            raise ValueError(f"Não foi possível encontrar a área ('area_ha' or 'area_total_ha') nos metadados da ROI {roi_id}")

        #file_pattern = re.compile(r'_(\d{4}-\d{2}-\d{2})_(B\d{2}A?)\.tif$')
        file_pattern = re.compile(r'_(\d{4}-\d{2}-\d{2})_(B\d{1,2}A?)\.tif$')
        
        files_by_date = defaultdict(dict)
        for tif_path in analysis_dir.rglob('*.tif'):
            match = file_pattern.search(tif_path.name)
            if match:
                date_str, band_name = match.groups()
                files_by_date[date_str][band_name] = tif_path
        
        if not files_by_date:
            raise FileNotFoundError("Nenhum arquivo .tif com nome padronizado (AAAA-MM-DD_BXX.tif) foi encontrado no ZIP.")

        for date_str, band_paths_dict in files_by_date.items():
            logger.info(f"[Job {job_id}] Processando data: {date_str}")
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
            await queries.save_analysis_results(job_id=job_id, results=results_to_save)
        
        await queries.update_job_status(job_id=job_id, status="COMPLETED")
        logger.info(f"[Job {job_id}] Análise concluída com sucesso.")

    except Exception as e:
        logger.error(f"[Job {job_id}] Erro na tarefa de background: {e}", exc_info=True)
        await queries.update_job_status(job_id=job_id, status="FAILED", error_message=str(e))
    finally:
        cleanup_temp_files(zip_path.parent)
        logger.info(f"[Job {job_id}] Limpeza dos arquivos temporários concluída.")


@router.post(
    "/upload-analysis",
    response_model=schemas.AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Análise] Faz upload de imagens para análise"
)
async def upload_for_analysis(
    background_tasks: BackgroundTasks,
    roi_id: int = Form(...),
    file: UploadFile = File(..., description="Arquivo .zip contendo as pastas de imagens."),
    current_user: dict = Depends(get_current_user)
):
    """
    Recebe um pacote de imagens .zip para uma ROI específica, inicia um job de
    análise em background e retorna o ID do job para consulta futura.
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="O arquivo deve ser no formato .zip")

    # Verifica se a ROI pertence ao usuário
    roi = await obter_roi_por_id(roi_id=roi_id, user_id=current_user['id'])
    if not roi:
        raise HTTPException(status_code=404, detail=f"ROI com ID {roi_id} não encontrada ou não pertence ao usuário.")

    try:
        # Salva o arquivo ZIP temporariamente
        temp_zip_path = save_uploaded_files([file])

        # Cria o job no banco de dados
        job_id = await queries.create_analysis_job(user_id=current_user['id'], roi_id=roi_id)

        # Adiciona a tarefa pesada para ser executada em background
        background_tasks.add_task(
            run_analysis_in_background,
            job_id=job_id,
            zip_path=temp_zip_path / file.filename,
            roi_id=roi_id,
            user_id=current_user['id']
        )
        
        return {
            "job_id": job_id,
            "roi_id": roi_id,
            "status": "PENDING",
            "message": "O job de análise foi criado e está na fila para processamento."
        }
    except Exception as e:
        logger.error(f"Erro ao iniciar o job de upload para análise: {e}", exc_info=True)
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