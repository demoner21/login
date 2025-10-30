import logging
from typing import List, Optional, Dict
from datetime import date
import asyncpg
import joblib
from pathlib import Path
from . import schemas # Importa o schema de paths

logger = logging.getLogger(__name__)

async def get_active_modelos(conn: asyncpg.Connection) -> List[Dict]:
    """Lista todos os modelos de ATR que estão marcados como 'ativos'."""
    query = """
        SELECT id, nome, descricao, mes_referencia, variedade 
        FROM modelos_atr 
        WHERE ativo = true 
        ORDER BY variedade, mes_referencia DESC
    """
    results = await conn.fetch(query)
    return [dict(row) for row in results]

async def get_suggested_modelo(
    conn: asyncpg.Connection, 
    data_referencia: date, 
    variedade: str
) -> Optional[Dict]:
    """
    Sugere o modelo mais apropriado com base em uma data E na variedade.
    """
    query = """
        SELECT id, nome, descricao, mes_referencia, variedade 
        FROM modelos_atr 
        WHERE mes_referencia <= $1 
          AND variedade = $2
          AND ativo = true 
        ORDER BY mes_referencia DESC 
        LIMIT 1
    """
    result = await conn.fetchrow(query, data_referencia, variedade)
    return dict(result) if result else None

async def get_model_paths(conn: asyncpg.Connection, modelo_id: int) -> Optional[schemas.ModeloATRPaths]:
    """Busca os caminhos dos artefatos de um modelo específico no DB."""
    query = """
        SELECT caminho_modelo_joblib, caminho_estatisticas_joblib, caminho_features_joblib
        FROM modelos_atr
        WHERE id = $1 AND ativo = true
    """
    result = await conn.fetchrow(query, modelo_id)
    if not result:
        logger.error(f"Nenhum modelo ativo encontrado para o ID: {modelo_id}")
        return None
    return schemas.ModeloATRPaths(**dict(result))

async def load_model_artifacts_from_paths(paths: schemas.ModeloATRPaths) -> Dict:
    """
    Carrega os arquivos .joblib do disco a partir dos caminhos fornecidos.
    Esta função é síncrona (I/O de disco), mas será chamada em um contexto async.
    """
    try:
        # Usamos os nomes de atributos do schema
        model = joblib.load(paths.caminho_modelo_joblib)
        stats = joblib.load(paths.caminho_estatisticas_joblib)
        features = joblib.load(paths.caminho_features_joblib)
        
        logger.info(f"Artefatos carregados para o modelo: {paths.caminho_modelo_joblib}")
        
        return {
            "model": model,
            "feature_stats": stats,
            "model_feature_list": features
        }
    except FileNotFoundError as e:
        logger.error(f"Erro ao carregar artefato do modelo: {e}", exc_info=True)
        raise ValueError(f"Arquivo de modelo não encontrado: {e.filename}")
    except Exception as e:
        logger.error(f"Erro desconhecido ao carregar modelo: {e}", exc_info=True)
        raise