import os
from dotenv import load_dotenv

# Garante que o .env seja carregado
load_dotenv()


class Settings:
    """
    Centraliza todas as configurações da aplicação lidas a partir
    de variáveis de ambiente.
    """
    # --- Configurações do Banco de Dados ---
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_NAME: str = os.getenv("DB_NAME")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))

    SECRET_KEY: str = os.getenv("SECRET_KEY")

    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))
    REFRESH_THRESHOLD_MINUTES: int = int(
        os.getenv("REFRESH_THRESHOLD_MINUTES"))

    # --- Configurações do Google Earth Engine ---
    EE_PROJECT: str = os.getenv("EE_PROJECT")
    EE_JSON_KEY_PATH: str = os.getenv("EE_JSON_KEY_PATH")
    DEFAULT_SERVICE_ACCOUNT: str = os.getenv("DEFAULT_SERVICE_ACCOUNT")

    # --- Configurações de Segurança Adicionais (Opcionais) ---
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS"))
    ACCOUNT_LOCK_TIME_MINUTES: int = int(
        os.getenv("ACCOUNT_LOCK_TIME_MINUTES"))

    # --- Campos Opcionais do JWT (se utilizados) ---
    JWT_ISSUER: str = os.getenv("JWT_ISSUER")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE")


# Instância única para ser importada em outros locais da aplicação
settings = Settings()
