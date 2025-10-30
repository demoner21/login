from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date

class ModeloATRResponse(BaseModel):
    """Schema para retornar informações de um modelo de ATR."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    nome: str
    descricao: Optional[str] = None
    mes_referencia: date

class ModeloATRPaths(BaseModel):
    """Schema interno para transportar os caminhos dos artefatos do modelo."""
    caminho_modelo_joblib: str
    caminho_estatisticas_joblib: str
    caminho_features_joblib: str