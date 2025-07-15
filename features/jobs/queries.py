import logging
from uuid import UUID
from database.session import with_db_connection

logger = logging.getLogger(__name__)

@with_db_connection
async def create_job(conn, *, user_id: int) -> UUID:
    """Cria um novo registro de job e retorna seu UUID."""
    query = "INSERT INTO jobs (user_id) VALUES ($1) RETURNING job_id"
    job_id = await conn.fetchval(query, user_id)
    logger.info(f"Criado Job com ID: {job_id} para o usuário {user_id}.")
    return job_id

@with_db_connection
async def get_job_by_id(conn, *, job_id: UUID, user_id: int) -> dict:
    """Busca um job pelo seu ID, verificando a propriedade do usuário."""
    query = "SELECT job_id, status, message, result_path, created_at, updated_at FROM jobs WHERE job_id = $1 AND user_id = $2"
    job = await conn.fetchrow(query, job_id, user_id)
    return dict(job) if job else None

@with_db_connection
async def update_job_status(conn, *, job_id: UUID, status: str, message: str = None, result_path: str = None):
    """Atualiza o status, mensagem e caminho de resultado de um job."""
    query = """
        UPDATE jobs
        SET status = $2, message = $3, result_path = $4
        WHERE job_id = $1
    """
    await conn.execute(query, job_id, status, message, result_path)
    logger.info(f"Status do Job {job_id} atualizado para: {status}")