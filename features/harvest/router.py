import logging
from typing import List
from datetime import date
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
import asyncpg
from asyncpg.exceptions import UniqueViolationError

from features.auth.dependencies import get_current_user
from database.session import get_db_connection
from . import queries, schemas

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/",
    response_model=schemas.ProgramacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Programação] Agenda um talhão para colheita"
)
async def create_harvest_schedule(
    data: schemas.ProgramacaoCreate,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Cria um novo agendamento de colheita para um talhão.
    
    - **talhao_id**: ID do talhão (ROI do tipo 'TALHAO').
    - **data_prevista_colheita**: Data futura da colheita.
    - **modelo_id_sugerido**: ID do modelo (de `modelos_atr`) que será usado.
    """
    try:
        user_id = current_user['id']
        new_schedule = await queries.create_programacao(conn, user_id, data)
        
        # O 'ProgramacaoResponse' padrão (não agrupado) é suficiente aqui
        return new_schedule
        
    except UniqueViolationError:
        logger.warning(f"Tentativa de agendamento duplicado: Talhão {data.talhao_id} na data {data.data_prevista_colheita}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este talhão já está agendado para esta data."
        )
    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno ao criar agendamento.")

@router.get(
    "/",
    response_model=List[schemas.HarvestSchedulePropertyGroupingResponse], # <-- MUDANÇA AQUI
    summary="[Programação] Lista os agendamentos de colheita (Agrupados)"
)
async def list_harvest_schedules(
    start_date: date = Query(..., description="Data de início (AAAA-MM-DD)"),
    end_date: date = Query(..., description="Data de fim (AAAA-MM-DD)"),
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Lista todos os agendamentos de colheita para o usuário
    dentro de um intervalo de datas, RETORNANDO-OS AGRUPADOS
    POR PROPRIEDADE e então POR DATA.
    """
    try:
        user_id = current_user['id']
        
        # 1. Busca a lista "plana" de agendamentos (a query já faz o JOIN)
        flat_schedules = await queries.list_programacao_by_user(conn, user_id, start_date, end_date)
        
        # 2. Lógica de Agrupamento em Python
        # Estrutura: { "Nome da Propriedade": { "data": [lista_de_talhoes], ... }, ... }
        propriedades_map = defaultdict(lambda: defaultdict(list))
        
        for item in flat_schedules:
            prop_nome = item['nome_propriedade'] or "Propriedade Desconhecida"
            data_colheita = item['data_prevista_colheita']
            
            # Monta o objeto 'Talhao' para a resposta
            talhao_obj = {
                "id": item['id'],
                "talhao_id": item['talhao_id'],
                "talhao_nome": item['talhao_nome'],
                "status": item['status'],
                "modelo_id_sugerido": item['modelo_id_sugerido']
            }
            propriedades_map[prop_nome][data_colheita].append(talhao_obj)
            
        # 3. Converte os dicionários aninhados na lista de resposta (schema)
        final_response = []
        for prop_nome, datas_map in propriedades_map.items():
            agendamentos_por_data = []
            
            for data, talhoes_list in datas_map.items():
                agendamentos_por_data.append({
                    "data_prevista_colheita": data,
                    "talhoes_agendados": talhoes_list
                })
            
            # Ordena os agendamentos pela data
            agendamentos_por_data.sort(key=lambda x: x['data_prevista_colheita'])
            
            final_response.append({
                "propriedade_nome": prop_nome,
                "agendamentos_por_data": agendamentos_por_data
            })
            
        # Ordena a resposta final pelo nome da propriedade
        final_response.sort(key=lambda x: x['propriedade_nome'])
        
        return final_response
        
    except Exception as e:
        logger.error(f"Erro ao listar agendamentos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar agendamentos.")

@router.delete(
    "/{programacao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Programação] Remove um agendamento"
)
async def delete_harvest_schedule(
    programacao_id: int,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Deleta um item da programação de colheita.
    """
    try:
        user_id = current_user['id']
        deleted = await queries.delete_programacao(conn, user_id, programacao_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agendamento não encontrado ou não pertence ao usuário."
            )
        # Retorna 204 No Content (sem corpo)
        return
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar agendamento: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno ao deletar agendamento.")