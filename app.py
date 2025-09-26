import os
import logging
from contextlib import asynccontextmanager

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse

from config import settings
from features.analysis.router import router as analysis_router
from features.auth.router import router as auth_router
from features.roi.router import router as roi_router
from features.users.router import router as users_router
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

    yield

    # 1.3. Encerramento
    logger.info("Encerrando servidor...")
    if hasattr(app.state, 'pool') and app.state.pool:
        await app.state.pool.close()
        logger.info("Pool de conexões fechado")

templates = Jinja2Templates(directory="static")

# 2. Criação do app FastAPI
app = FastAPI(
    title="Portal Multiespectral - Refatorado",
    version="1.0.0",
    description="Sistema de detecção de TCH & ATR por imagens de satélite",
    lifespan=lifespan
)

allowed_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://seu-dominio-de-producao.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
#app.add_middleware(TokenRefreshMiddleware)

# 4. Rotas da API
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Autenticação"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Usuários"])
app.include_router(roi_router, prefix="/api/v1/roi", tags=["Regiões de Interesse"])
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["Análise de TCH & ATR"])

app.mount("/static", StaticFiles(directory="static"), name="static")

# 6. Rotas de Página (Frontend)
@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def get_login_page(request: Request):
    """Serve a página de login na rota raiz."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse, tags=["Frontend"])
async def get_login_page_redirect(request: Request):
    """Serve a página de login para compatibilidade."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["Frontend"])
async def get_dashboard_page(request: Request):
    """Serve a página do dashboard usando templates."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse, tags=["Frontend"])
async def get_settings_page(request: Request):
    """Serve a página de configurações usando templates."""
    return templates.TemplateResponse("settings.html", {"request": request})

# Esta linha faz o FastAPI servir arquivos estáticos de forma redundante.
# O Nginx já lida com isso. Comente-a para evitar conflitos.
#app.mount("/", StaticFiles(directory="static"), name="static")
