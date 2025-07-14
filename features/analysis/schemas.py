from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

class AnalysisJobResponse(BaseModel):
    """Resposta ao iniciar um novo job de análise."""
    job_id: int
    roi_id: int
    status: str
    message: str

class AnalysisResultSchema(BaseModel):
    """Schema para um único resultado de análise."""
    date_analyzed: date
    predicted_atr: float

    class Config:
        from_attributes = True

class AnalysisJobStatusResponse(BaseModel):
    """Resposta detalhada ao consultar o status de um job."""
    job_id: int
    roi_id: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: List[AnalysisResultSchema] = Field(default_factory=list)
    error_message: Optional[str] = None

    class Config:
        from_attributes = True