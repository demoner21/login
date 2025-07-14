import logging
import json
from datetime import datetime
from typing import List, Dict

from database.session import with_db_connection, with_db_connection_bg

logger = logging.getLogger(__name__)

@with_db_connection
async def create_analysis_job(conn, *, user_id: int, roi_id: int) -> int:
    """Cria um novo registro de job de análise e retorna o ID."""
    query = "INSERT INTO analysis_jobs (user_id, roi_id) VALUES ($1, $2) RETURNING job_id"
    job_id = await conn.fetchval(query, user_id, roi_id)
    logger.info(f"Criado job de análise com ID: {job_id} para o usuário {user_id} e ROI {roi_id}.")
    return job_id

@with_db_connection
async def update_job_status(conn, *, job_id: int, status: str, error_message: str = None):
    """Atualiza o status e a data de conclusão de um job."""
    completed_at = datetime.now() if status in ['COMPLETED', 'FAILED'] else None
    query = """
        UPDATE analysis_jobs
        SET status = $2, completed_at = $3, error_message = $4
        WHERE job_id = $1
    """
    await conn.execute(query, job_id, status, completed_at, error_message)
    logger.info(f"Status do job {job_id} atualizado para: {status}")

@with_db_connection
async def save_analysis_results(conn, *, job_id: int, results: List[Dict]):
    """Salva os resultados de predição para um job."""
    query = "INSERT INTO analysis_results (job_id, date_analyzed, predicted_atr) VALUES ($1, $2, $3)"
    # Awaited executemany
    await conn.executemany(query, [(job_id, r['date_analyzed'], r['predicted_atr']) for r in results])
    logger.info(f"Salvos {len(results)} resultados para o job {job_id}.")

@with_db_connection
async def get_job_with_results(conn, *, job_id: int, user_id: int) -> Dict:
    """Busca um job e seus resultados associados, verificando a propriedade do usuário."""
    job_query = """
        SELECT job_id, roi_id, status, created_at, completed_at, error_message
        FROM analysis_jobs WHERE job_id = $1 AND user_id = $2
    """
    job_details = await conn.fetchrow(job_query, job_id, user_id)
    if not job_details:
        return None

    results_query = "SELECT date_analyzed, predicted_atr FROM analysis_results WHERE job_id = $1 ORDER BY date_analyzed"
    results = await conn.fetch(results_query, job_id)

    job_dict = dict(job_details)
    job_dict['results'] = [dict(r) for r in results]
    return job_dict

@with_db_connection_bg
async def create_analysis_job_bg(conn, *, user_id: int, roi_id: int) -> int:
    """Cria um novo registro de job de análise (seguro para background)."""
    query = "INSERT INTO analysis_jobs (user_id, roi_id) VALUES ($1, $2) RETURNING job_id"
    job_id = await conn.fetchval(query, user_id, roi_id)
    logger.info(f"BG Task: Criado job de análise com ID: {job_id} para o usuário {user_id} e ROI {roi_id}.")
    return job_id

@with_db_connection_bg
async def update_job_status_bg(conn, *, job_id: int, status: str, error_message: str = None):
    """Atualiza o status de um job (seguro para background)."""
    completed_at = datetime.now() if status in ['COMPLETED', 'FAILED'] else None
    query = "UPDATE analysis_jobs SET status = $2, completed_at = $3, error_message = $4 WHERE job_id = $1"
    await conn.execute(query, job_id, status, completed_at, error_message)
    logger.info(f"BG Task: Status do job {job_id} atualizado para: {status}")