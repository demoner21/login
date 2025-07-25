import zxcvbn
from passlib.context import CryptContext
import logging

logger = logging.getLogger(__name__)
PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def is_password_strong(password: str) -> bool:
    """Verifica a força da senha usando zxcvbn"""
    if not password:
        return False

    result = zxcvbn.zxcvbn(password)
    # Requer score mínimo de 3 (de 0 a 4) e pelo menos 8 caracteres
    return result["score"] >= 4 and len(password) >= 8


def get_password_hash(password: str) -> str:
    """
    Gera um hash seguro para a senha, com validação de força.

    Args:
        password: Senha em texto puro

    Returns:
        str: Hash da senha

    Raises:
        ValueError: Se a senha não for forte o suficiente
    """
    if not password:
        raise ValueError("A senha não pode estar vazia")

    if not is_password_strong(password):
        raise ValueError(
            "A senha não atende aos requisitos de segurança. "
            "Deve ter pelo menos 8 caracteres, incluindo maiúsculas, "
            "minúsculas e números."
        )

    # Remove espaços em branco extras e gera o hash
    return PWD_CONTEXT.hash(password.strip())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha corresponde ao hash armazenado.

    Args:
        plain_password: Senha em texto puro
        hashed_password: Hash armazenado no banco

    Returns:
        bool: True se a senha corresponder, False caso contrário
    """
    if not plain_password or not hashed_password:
        return False

    try:
        # Remove espaços em branco extras e verifica
        return PWD_CONTEXT.verify(plain_password.strip(), hashed_password)
    except Exception as e:
        logger.error(f"Erro na verificação de senha: {str(e)}")
        return False
