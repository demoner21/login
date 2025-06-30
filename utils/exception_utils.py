from functools import wraps
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

def handle_exceptions(func):
    """
    Decorador para centralizar o tratamento de exceções.
    Preserva a assinatura da função original para o FastAPI.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Erro ao executar a função: {e}", exc_info=True)
            raise HTTPException(
                status_code=400, detail=f"Erro ao processar a requisição: {str(e)}"
            )
    return wrapper