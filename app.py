import logging
from contextlib import asynccontextmanager

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from features.analysis.router import router as analysis_router
from features.auth.router import router as auth_router
from features.roi.router import router as roi_router
from features.users.router import router as users_router
from middleware.session_middleware import TokenRefreshMiddleware
from services.earth_engine_initializer import initialize_earth_engine
from utils.logging import setup_logging

# 1. Configuração inicial
load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação com:
    - Inicialização de recursos antes do yield
    - Limpeza de recursos após o yield
    """
    logger.info("Iniciando servidor...")
    
    # 1.1. Inicialização do banco de dados
    logger.info("Criando pool de conexões com o banco de dados...")
    try:
        app.state.pool = await asyncpg.create_pool(
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            min_size=5,
            max_size=20,
            command_timeout=60,
        )
        logger.info("Pool de conexões estabelecido com sucesso")
    except Exception as e:
        logger.critical(f"Falha ao criar pool de conexões: {e}", exc_info=True)
        raise

    # 1.2. Inicialização do Google Earth Engine
    try:
        initialize_earth_engine()
        logger.info("Google Earth Engine inicializado com sucesso")
    except Exception as e:
        logger.critical(f"Falha ao inicializar Google Earth Engine: {e}", exc_info=True)
        raise

    yield  # A aplicação roda aqui

    # 1.3. Encerramento
    logger.info("Encerrando servidor...")
    if hasattr(app.state, 'pool') and app.state.pool:
        await app.state.pool.close()
        logger.info("Pool de conexões fechado")

# 2. Criação do app FastAPI
app = FastAPI(
    title="Portal Multiespectral - Refatorado",
    version="1.0.0",
    description="Sistema de detecção de TCH & ATR por imagens de satélite",
    lifespan=lifespan
)

# 3. Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restrinja aos domínios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TokenRefreshMiddleware)

# 4. Rotas
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Autenticação"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Usuários"])
app.include_router(roi_router, prefix="/api/v1/roi", tags=["Regiões de Interesse"])
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["Análise de TCH & ATR"])

# 5. Arquivos estáticos
#app.mount("/static", StaticFiles(directory="static", html=True), name="static")
#$ gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000

# 6. Health Check
@app.get("/", tags=["Root"])
async def read_root():
    """Endpoint de health check da API"""
    return {"message": "Bem-vindo à API do Portal Multiespectral"}