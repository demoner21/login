from features.roi.router import router as roi_router
from features.auth.router import router as auth_router
from middleware.session_middleware import TokenRefreshMiddleware
from utils.logging import setup_logging
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()


# 1. Configurar o logging
setup_logging()
logger = logging.getLogger(__name__)

# 2. Criar a instância do aplicativo FastAPI
app = FastAPI(
    title="Portal Multespectral - Refatorado",
    version="1.0.0",
    description="Sistema de detecção de TCH & ATR por imagens de satélite."
)

# 3. Adicionar Middlewares Essenciais
# Middleware de CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restrinja para os domínios do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TokenRefreshMiddleware)
# 4. Incluir as Rotas da Aplicação
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Autenticação"])
app.include_router(roi_router, prefix="/api/v1/roi",
                   tags=["Regiões de Interesse"])

# Monta um diretório estático (CSS, JS, Imagens) para ser servido
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


@app.on_event("startup")
async def startup_event():
    logger.info("Servidor iniciando e pronto para receber requisições.")


@app.get("/", tags=["Root"])
async def read_root():
    """
    Endpoint raiz para verificar se a API está no ar.
    """
    return {"message": "Bem-vindo à API do Portal Multiespectral"}
