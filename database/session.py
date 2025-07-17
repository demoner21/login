import asyncpg
import logging
from config import settings
from functools import wraps
from config import settings
from utils.exception_utils import handle_exceptions
from fastapi import Request, Depends, HTTPException

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

def with_db_connection_bg(func):
    """
    Decorador de conexão com o DB para tarefas em background.
    Não lança HTTPException, apenas registra o erro e o relança.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        conn = None
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            logger.info("BG Task: Conexão estabelecida")
            result = await func(conn, *args, **kwargs)
            logger.info("BG Task: Operação concluída")
            return result
        except Exception as e:
            logger.error(f"BG Task: Erro de banco de dados: {str(e)}", exc_info=True)
            raise  # Relança a exceção original para ser tratada pela tarefa
        finally:
            if conn:
                await conn.close()
                logger.info("BG Task: Conexão fechada")
    return wrapper

async def get_db_connection(request: Request) -> asyncpg.Connection:
    """
    Dependência do FastAPI que adquire uma conexão do pool para uma requisição
    e a libera automaticamente no final.
    """
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(
            status_code=503, 
            detail="Serviço indisponível: pool de conexões com o banco de dados não foi inicializado."
        )

    # Adquire uma conexão do pool
    conn = await pool.acquire()
    logger.info(f"Conexão {id(conn)} adquirida do pool.")
    try:
        # Disponibiliza a conexão para a rota
        yield conn
    finally:
        # Libera a conexão de volta para o pool quando a requisição termina
        await pool.release(conn)
        logger.info(f"Conexão {id(conn)} liberada de volta para o pool.")