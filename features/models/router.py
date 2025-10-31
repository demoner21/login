import logging
from typing import List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
import asyncpg

from features.auth.dependencies import get_current_user
from database.session import get_db_connection
from . import queries, schemas

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/",
    response_model=List[schemas.ModeloATRResponse],
    summary="[Modelos] Lista modelos de análise ATR ativos"
)
async def list_active_models(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Retorna uma lista de todos os modelos de análise de ATR
    que estão ativos no sistema, ordenados por variedade e data.
    """
    try:
        modelos = await queries.get_active_modelos(conn)
        return modelos
    except Exception as e:
        logger.error(f"Erro ao listar modelos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar modelos.")

@router.get(
    "/suggest",
    response_model=schemas.ModeloATRResponse,
    summary="[Modelos] Sugere um modelo baseado na data e variedade"
)
async def suggest_model(
    data: date = Query(..., description="Data de referência (ex: data da colheita) no formato AAAA-MM-DD."),
    variedade: str = Query(..., description="Nome da variedade do talhão (ex: 'CTC-04')."),
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Sugere o modelo de análise mais apropriado com base na
    DATA DE REFERÊNCIA e na VARIEDADE do talhão.
    
    Retorna 404 com mensagens específicas se o modelo não for encontrado.
    """
    try:
        # 1. Tenta encontrar o modelo ideal
        modelo = await queries.get_suggested_modelo(conn, data, variedade)
        
        if modelo:
            return modelo # Sucesso!
        
        # 2. Se não encontrou (modelo is None), investiga o porquê
        variedade_existe = await queries.check_variedade_exists(conn, variedade)
        
        if not variedade_existe:
            # Causa 1: A variedade nem existe no sistema de modelos
            logger.warning(f"Sugestão falhou: Nenhum modelo encontrado para a variedade: {variedade}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Não há modelos de análise disponíveis para a variedade '{variedade}'."
            )
        else:
            # Causa 2: A variedade existe, mas não para esta data
            logger.warning(f"Sugestão falhou: A variedade '{variedade}' existe, mas não para a data {data}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Não há modelo disponível para a variedade '{variedade}' na data '{data}'. (Modelos podem existir para outros meses)."
            )
            
    except HTTPException:
        raise # Re-levanta a HTTPException que acabamos de criar
    except Exception as e:
        logger.error(f"Erro ao sugerir modelo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao sugerir modelo.")