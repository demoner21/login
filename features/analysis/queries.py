import logging
import json
from datetime import datetime
import asyncpg
from typing import List, Dict, Optional

from database.session import with_db_connection, with_db_connection_bg

logger = logging.getLogger(__name__)

@with_db_connection
async def create_analysis_job(conn, *, user_id: int, roi_id: Optional[int] = None, parent_job_id: Optional[int] = None) -> int:
    """Cria um novo registro de job de análise e retorna o ID."""
    query = "INSERT INTO analysis_jobs (user_id, roi_id, parent_job_id) VALUES ($1, $2, $3) RETURNING job_id"
    job_id = await conn.fetchval(query, user_id, roi_id, parent_job_id)
    if parent_job_id:
        logger.info(f"Criado job de análise filho com ID: {job_id} para o ROI {roi_id}, filho de {parent_job_id}.")
    else:
        logger.info(f"Criado job de análise pai com ID: {job_id} para o usuário {user_id}.")
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
    await conn.executemany(query, [(job_id, r['date_analyzed'], r['predicted_atr']) for r in results])
    logger.info(f"Salvos {len(results)} resultados para o job {job_id}.")

@with_db_connection
async def get_job_with_results(conn, *, job_id: int, user_id: int) -> Optional[Dict]:
    """
    Busca um job e seus resultados. Se for um job pai, busca também todos os jobs filhos
    e seus respectivos resultados de forma otimizada.
    """
    # 1. Buscar o job principal (pai) e todos os seus filhos diretos em uma única query
    all_jobs_query = """
        SELECT job_id, roi_id, status, created_at, completed_at, error_message, parent_job_id
        FROM analysis_jobs
        WHERE (job_id = $1 AND user_id = $2) OR (parent_job_id = $1 AND user_id = $2)
        ORDER BY parent_job_id NULLS FIRST, job_id; -- Garante que o pai venha primeiro
    """
    all_job_records = await conn.fetch(all_jobs_query, job_id, user_id)

    if not all_job_records:
        return None

    all_job_ids = [j['job_id'] for j in all_job_records]

    # 2. Buscar todos os resultados para todos os jobs encontrados de uma vez
    results_query = "SELECT job_id, date_analyzed, predicted_atr FROM analysis_results WHERE job_id = ANY($1::int[]) ORDER BY date_analyzed"
    all_results_records = await conn.fetch(results_query, all_job_ids)

    # 3. Mapear resultados por job_id para fácil acesso
    results_map = {}
    for res in all_results_records:
        res_job_id = res['job_id']
        if res_job_id not in results_map:
            results_map[res_job_id] = []
        results_map[res_job_id].append(dict(res))

    # 4. Montar a estrutura hierárquica
    job_map = {j['job_id']: dict(j) for j in all_job_records}
    root_job = None

    for j_id, job_data in job_map.items():
        job_data['results'] = results_map.get(j_id, [])
        job_data['child_jobs'] = [] # Inicializa a lista de filhos

        parent_id = job_data.get('parent_job_id')
        if parent_id in job_map:
            job_map[parent_id]['child_jobs'].append(job_data)
        elif job_data['job_id'] == job_id: # É o job raiz que foi solicitado
            root_job = job_data
            
    return root_job

@with_db_connection_bg
async def create_analysis_job(conn: asyncpg.Connection, user_id: int, roi_id: Optional[int], parent_job_id: Optional[int] = None) -> int:
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