import logging
from typing import List, Optional, Dict
from datetime import date
import asyncpg
from . import schemas
import asyncpg

logger = logging.getLogger(__name__)

async def create_programacao(
    conn: asyncpg.Connection, 
    user_id: int, 
    data: schemas.ProgramacaoCreate
) -> Dict:
    """
    Insere um novo agendamento de colheita no banco de dados.
    """
    query = """
        INSERT INTO programacao_colheita
        (user_id, talhao_id, data_prevista_colheita, modelo_id_sugerido, status)
        VALUES ($1, $2, $3, $4, 'PENDENTE')
        RETURNING id, user_id, talhao_id, data_prevista_colheita, 
                  modelo_id_sugerido, status, data_criacao
    """
    # Nota: A constraint UNIQUE no DB  vai prevenir duplicatas
    # (user_id, talhao_id, data_prevista_colheita)
    new_record = await conn.fetchrow(
        query,
        user_id,
        data.talhao_id,
        data.data_prevista_colheita,
        data.modelo_id_sugerido
    )
    return dict(new_record)

async def list_programacao_by_user(
    conn: asyncpg.Connection, 
    user_id: int, 
    start_date: date, 
    end_date: date
) -> List[Dict]:
    """
    Lista todos os agendamentos de um usuário dentro de um intervalo de datas.
    Junta com a tabela 'regiao_de_interesse' para obter os nomes.
    """
    query = """
        SELECT 
            p.id,
            p.user_id,
            p.talhao_id,
            p.data_prevista_colheita,
            p.modelo_id_sugerido,
            p.status,
            p.data_criacao,
            r.nome AS talhao_nome,
            r.nome_propriedade
        FROM 
            programacao_colheita p
        JOIN 
            regiao_de_interesse r ON p.talhao_id = r.roi_id
        WHERE 
            p.user_id = $1 
            AND r.user_id = $1 -- Garante que o talhão também é do usuário
            AND p.data_prevista_colheita BETWEEN $2 AND $3
        ORDER BY 
            p.data_prevista_colheita ASC;
    """
    results = await conn.fetch(query, user_id, start_date, end_date)
    return [dict(row) for row in results]

async def delete_programacao(
    conn: asyncpg.Connection, 
    user_id: int, 
    programacao_id: int
) -> bool:
    """
    Deleta um agendamento específico, verificando se pertence ao usuário.
    """
    query = """
        DELETE FROM programacao_colheita
        WHERE id = $1 AND user_id = $2
        RETURNING id
    """
    deleted_id = await conn.fetchval(query, programacao_id, user_id)
    return deleted_id is not None