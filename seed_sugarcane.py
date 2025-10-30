import asyncio
import asyncpg
import logging
from pathlib import Path
from config import settings
from datetime import date

# --- Configurações ---
BASE_MODEL_DIR = Path("models/variedades") 
DB_CONFIG = {
    "user": settings.DB_USER,
    "password": settings.DB_PASSWORD,
    "database": settings.DB_NAME,
    "host": settings.DB_HOST,
    "port": settings.DB_PORT,
}

# Mapeia os nomes das pastas de mês para números
MONTH_MAP = {
    'janeiro': '01', 'fevereiro': '02', 'marco': '03', 'abril': '04',
    'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
    'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
}
# Ano base para o 'mes_referencia'.
# Use o ano que preferir, o log mostrou que você está usando 2024.
BASE_YEAR = "2024" 

# Nomes dos arquivos de modelo esperados
MODEL_FILE = "melhor_modelo.joblib"
STATS_FILE = "metadata.joblib"
FEATURES_FILE = "feature_rankings.joblib"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def seed_models():
    conn = None
    try:
        logger.info(f"Tentando conectar com a config: {DB_CONFIG}")
        conn = await asyncpg.connect(**DB_CONFIG)
        logger.info("Conectado ao banco de dados...")
        
        await conn.execute("TRUNCATE TABLE public.modelos_atr RESTART IDENTITY CASCADE;")
        logger.info("Tabela 'modelos_atr' limpa.")

        model_count = 0
        
        for variedade_path in BASE_MODEL_DIR.iterdir():
            if not variedade_path.is_dir():
                continue
            
            variedade_nome = variedade_path.name
            
            for month_path in variedade_path.iterdir():
                if not month_path.is_dir():
                    continue
                
                try:
                    mes_nome = month_path.name.split('_')[-1].lower()
                    mes_num = MONTH_MAP.get(mes_nome)
                    
                    if not mes_num:
                        logger.warning(f"Pasta de mês ignorada (formato inválido): {month_path.name}")
                        continue
                        
                    mes_referencia_date_obj = date(int(BASE_YEAR), int(mes_num), 1)

                    caminho_modelo = month_path / MODEL_FILE
                    caminho_stats = month_path / STATS_FILE
                    caminho_features = month_path / FEATURES_FILE

                    if not (caminho_modelo.exists() and caminho_stats.exists() and caminho_features.exists()):
                        logger.error(f"ERRO: Faltando arquivos .joblib em: {month_path}")
                        continue
                    
                    nome_modelo = f"{variedade_nome} - {mes_nome.capitalize()}"
                    descricao_modelo = f"Modelo de ATR para variedade {variedade_nome}, otimizado para {mes_nome}."
                    
                    query = """
                        INSERT INTO public.modelos_atr
                        (nome, descricao, mes_referencia, variedade, 
                         caminho_modelo_joblib, caminho_estatisticas_joblib, caminho_features_joblib, ativo)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, true)
                        ON CONFLICT (variedade, mes_referencia) DO NOTHING;
                    """
                    
                    await conn.execute(
                        query,
                        nome_modelo,
                        descricao_modelo,
                        mes_referencia_date_obj,
                        variedade_nome,
                        str(caminho_modelo),
                        str(caminho_stats),
                        str(caminho_features)
                    )
                    
                    logger.info(f"Modelo Inserido: {nome_modelo}")
                    model_count += 1

                except Exception as e:
                    logger.error(f"Falha ao processar {month_path}: {e}", exc_info=True)

        logger.info(f"Processamento concluído. {model_count} modelos inseridos.")

    except asyncpg.exceptions.InvalidPasswordError:
        logger.error("Falha na autenticação com o banco. Verifique seu .env")
    except Exception as e:
        logger.error(f"Erro ao conectar ou popular o banco: {e}", exc_info=True)
    finally:
        if conn:
            await conn.close()
            logger.info("Conexão com o banco fechada.")

if __name__ == "__main__":
    asyncio.run(seed_models())