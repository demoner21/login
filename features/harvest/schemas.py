from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date, datetime

class ProgramacaoBase(BaseModel):
    """Schema base para a programação."""
    talhao_id: int
    data_prevista_colheita: date
    modelo_id_sugerido: int

class ProgramacaoCreate(ProgramacaoBase):
    """Schema para criar um novo agendamento."""
    pass

class ProgramacaoResponse(ProgramacaoBase):
    """Schema para retornar um agendamento completo, incluindo dados do talhão."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    status: str
    data_criacao: datetime
    
    # Campos adicionados do JOIN para facilitar o frontend
    talhao_nome: Optional[str] = None
    nome_propriedade: Optional[str] = None

class HarvestScheduleTalhaoResponse(BaseModel):
    """Schema interno para o talhão dentro de um agrupamento de data."""
    model_config = ConfigDict(from_attributes=True)
    
    programacao_id: int = Field(alias="id")
    talhao_id: int
    talhao_nome: Optional[str] = None
    status: str
    modelo_id_sugerido: int

class HarvestScheduleDateGroupingResponse(BaseModel):
    """Agrupamento de talhões agendados por data."""
    data_prevista_colheita: date
    talhoes_agendados: List[HarvestScheduleTalhaoResponse]

class HarvestSchedulePropertyGroupingResponse(BaseModel):
    """Resposta final agrupada por propriedade."""
    propriedade_nome: str
    agendamentos_por_data: List[HarvestScheduleDateGroupingResponse]