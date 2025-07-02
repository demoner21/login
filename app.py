import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routes.auth_routes import router as auth_router
from routes.roi_routes import router as roi_router
from utils.logging import setup_logging

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

# 4. Incluir as Rotas da Aplicação
app.include_router(auth_router, prefix="/api/v1")

app.include_router(roi_router, prefix="/api/v1") # <--- 2. ROTA DE ROI ADICIONADA

# Monta um diretório estático (CSS, JS, Imagens) para ser servido
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# 5. Adicionar um evento de startup para logar o início
@app.on_event("startup")
async def startup_event():
    logger.info("Servidor iniciando e pronto para receber requisições.")
# 6. Adicionar uma rota raiz para verificação
@app.get("/", tags=["Root"])
async def read_root():
    """
    Endpoint raiz para verificar se a API está no ar.
    """
    return {"message": "Bem-vindo à API do Portal Multiespectral"}