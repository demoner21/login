import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import FileResponse
from features.auth.dependencies import get_current_user
from features.jobs.queries import create_job
from features.roi.router import get_job_status_route, get_job_result_file
from . import schemas
from .service import report_service

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/reports", 
    tags=["Relatórios ATR (PDF)"]
)

@router.post(
    "/atr",
    response_model=schemas.ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[Relatório] Inicia a geração de um relatório de ATR em PDF"
)
async def request_atr_report(
    background_tasks: BackgroundTasks,
    request_data: schemas.ReportRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Inicia um job em background para gerar o relatório em PDF a partir de um job de análise concluído.
    """
    user_id = current_user['id']
    
    # 1. Gerar um novo job de download (UUID) para rastrear este relatório
    report_job_id = await create_job(user_id=user_id) 

    # 2. Disparar a tarefa em background
    background_tasks.add_task(
        report_service.generate_atr_report_background,
        report_job_id=report_job_id,
        user_id=user_id,
        analysis_job_id=request_data.job_id,
        threshold=request_data.threshold
    )
    
    return {
        "job_id": str(report_job_id),
        "message": "A geração do relatório foi iniciada em segundo plano."
    }

@router.get(
    "/jobs/{job_id}/status",
    summary="[Relatório] Consulta o status de um job de relatório"
)
async def get_report_job_status(job_id: UUID, current_user: dict = Depends(get_current_user)):
    """Consulta o status do job de geração de relatório."""
    # Reutiliza a lógica de status de job do módulo ROI
    return await get_job_status_route(job_id=job_id, current_user=current_user)

@router.get(
    "/jobs/{job_id}/result",
    response_class=FileResponse,
    summary="[Relatório] Baixa o relatório PDF de um job concluído"
)
async def get_report_result_file_route(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Retorna o arquivo PDF gerado."""
    # Reutiliza a lógica de download do módulo ROI (que gerencia o cleanup)
    return await get_job_result_file(job_id=job_id, background_tasks=background_tasks, current_user=current_user)