import asyncpg
import logging
from functools import wraps
from config import settings
from utils.exception_utils import handle_exceptions

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "user": settings.DB_USER,
    "password": settings.DB_PASSWORD,
    "database": settings.DB_NAME,
    "host": settings.DB_HOST,
    "port": settings.DB_PORT,
    "command_timeout": 60
}


def with_db_connection(func):
    """
    Decorador para gerenciar a conexão com o banco de dados.
    Preserva a assinatura original da função para o FastAPI.
    """
    @wraps(func)
    @handle_exceptions
    async def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            logger.info("Conexão estabelecida")
            # Injetando conn como primeiro argumento
            result = await func(conn, *args, **kwargs)
            logger.info("Operação concluída")
            return result
        except Exception as e:
            logger.error(f"Erro: {str(e)}")
            raise
        finally:
            if conn:
                await conn.close()
                logger.info("Conexão fechada")
    return wrapper
