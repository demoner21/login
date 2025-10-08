from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class ReportRequest(BaseModel):
    """Requisição para gerar um relatório em PDF para um job de análise."""
    job_id: int = Field(..., description="ID do job pai de análise que contém os resultados.")
    threshold: float = Field(0.0, description="Limiar de ATR para destaque na imagem do relatório.")

class ReportResponse(BaseModel):
    """Resposta com o ID do job de download do relatório."""
    job_id: str
    message: str