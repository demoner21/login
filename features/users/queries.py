import logging
from typing import Optional
from datetime import datetime, timedelta

from database.session import with_db_connection
from .service import get_password_hash, PWD_CONTEXT, verify_password

logger = logging.getLogger(__name__)
db_logger = logging.getLogger('database_operations')


@with_db_connection
async def inserir_usuario(conn, nome: str, email: str, senha: str, role: str = "user"):
    """
    Insere um novo usuário no banco de dados.

    Args:
        conn: Conexão com o banco
        nome: Nome completo do usuário
        email: Email do usuário (deve ser único)
        senha: Senha em texto puro (será hasheada)
        role: Perfil do usuário (padrão: 'user')

    Returns:
        None

    Raises:
        ValueError: Se a senha não for forte o suficiente
        asyncpg.exceptions.UniqueViolationError: Se o email já existir
    """
    hashed_password = get_password_hash(senha)
    await conn.execute("""
        INSERT INTO usuario (nome, email, senha, role)
        VALUES ($1, $2, $3, $4)
    """, nome, email, hashed_password, role)
    logger.info(f"Usuário {nome} inserido com sucesso!")


@with_db_connection
async def verificar_email_existente(conn, email: str) -> bool:
    """Verifica se um email já está cadastrado"""
    resultado = await conn.fetchval("""
        SELECT EXISTS(SELECT 1 FROM usuario WHERE email = $1)
    """, email)
    return resultado


@with_db_connection
async def get_user_by_email(conn, email: str):
    """
    Busca usuário por email com logs detalhados
    """
    db_logger.info(f"Buscando usuário com email: {email}")

    try:
        user = await conn.fetchrow("""
            SELECT id, nome, email, senha, role 
            FROM usuario 
            WHERE email = $1
        """, email)

        if user:
            db_logger.debug(f"Usuário encontrado: {dict(user)}")
            return dict(user)
        else:
            db_logger.warning(
                f"Nenhum usuário encontrado para o email: {email}")
            return None

    except Exception as e:
        db_logger.error(f"Erro ao buscar usuário: {str(e)}", exc_info=True)
        raise


async def get_user_by_email_conn(conn, user_id: int):
    # Esta função é um exemplo, você pode adaptar a sua `get_user_by_email`
    user = await conn.fetchrow("SELECT id, nome, email, senha, role FROM usuario WHERE id = $1", user_id)
    return dict(user) if user else None


@with_db_connection
async def store_refresh_token(conn, user_id: int, token: str) -> None:
    """Armazena o hash do refresh token no banco de dados."""
    hashed_token = PWD_CONTEXT.hash(token)
    expires_at = datetime.utcnow() + timedelta(days=1)  # Validade de 1 dia

    # Remove tokens antigos do mesmo usuário para garantir um token ativo por vez
    await conn.execute("DELETE FROM user_refresh_tokens WHERE user_id = $1", user_id)

    await conn.execute(
        """
        INSERT INTO user_refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
        """,
        user_id, hashed_token, expires_at
    )
    logger.info(f"Refresh token armazenado para o usuário ID {user_id}")


@with_db_connection
async def get_user_by_refresh_token(conn, token: str) -> Optional[dict]:
    """Busca um usuário a partir de um refresh token válido."""
    records = await conn.fetch("SELECT user_id, token_hash FROM user_refresh_tokens WHERE expires_at > NOW()")

    for record in records:
        if PWD_CONTEXT.verify(token, record['token_hash']):
            # Encontrou o token, agora remove para evitar reuso (base para rotação)
            await conn.execute("DELETE FROM user_refresh_tokens WHERE token_hash = $1", record['token_hash'])
            # Supõe uma função que usa uma conexão existente
            return await get_user_by_email_conn(conn, record['user_id'])

    return None


@with_db_connection
async def delete_user_refresh_tokens(conn, user_id: int) -> None:
    """Remove todos os refresh tokens de um usuário (para logout)."""
    await conn.execute("DELETE FROM user_refresh_tokens WHERE user_id = $1", user_id)
    logger.info(f"Refresh tokens removidos para o usuário ID {user_id}")


@with_db_connection
async def update_user_password(conn, email: str, new_password: str):
    """Atualiza a senha de um usuário"""
    hashed_password = get_password_hash(new_password)
    await conn.execute("""
        UPDATE usuario 
        SET senha = $1
        WHERE email = $2
    """, hashed_password, email)
    logger.info(f"Senha atualizada para o usuário {email}")
