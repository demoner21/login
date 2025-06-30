from functools import wraps
import asyncpg
from dotenv import load_dotenv
import logging
import os
from utils.exception_utils import handle_exceptions
from passlib.context import CryptContext
import zxcvbn

logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações do banco de dados
DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "command_timeout": 60
}

db_logger = logging.getLogger('database_operations')
db_logger.setLevel(logging.DEBUG)
PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

def is_password_strong(password: str) -> bool:
    """Verifica a força da senha usando zxcvbn"""
    if not password:
        return False
        
    result = zxcvbn.zxcvbn(password)
    # Requer score mínimo de 3 (de 0 a 4) e pelo menos 8 caracteres
    return result["score"] >= 0 and len(password) >= 3

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
            result = await func(conn, *args, **kwargs)  # Injetando conn como primeiro argumento
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
            db_logger.warning(f"Nenhum usuário encontrado para o email: {email}")
            return None
    
    except Exception as e:
        db_logger.error(f"Erro ao buscar usuário: {str(e)}", exc_info=True)
        raise

@with_db_connection
async def excluir_usuario_por_id(conn, id: int):
    """Exclui um usuário pelo ID"""
    await conn.execute("""
        DELETE FROM usuario WHERE id = $1
    """, id)
    logger.info(f"Usuário com id {id} excluído com sucesso!")

@with_db_connection
async def excluir_usuario_por_email(conn, email: str):
    """Exclui um usuário pelo email"""
    await conn.execute("""
        DELETE FROM usuario WHERE email = $1
    """, email)
    logger.info(f"Usuário com email {email} excluído com sucesso!")

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

@with_db_connection
async def get_user_roles(conn, email: str) -> list[str]:
    """Obtém os papéis/permissões de um usuário"""
    roles = await conn.fetchval("""
        SELECT role FROM usuario WHERE email = $1
    """, email)
    return roles.split(',') if roles else ['user']

def configure_logging():
    # Configurações para logs de autenticação
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # Log no console
            logging.FileHandler('authentication.log')  # Log em arquivo
        ]
    )

    
configure_logging()