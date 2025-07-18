from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, date


class AnalysisJobResponse(BaseModel):
    """Resposta ao iniciar um novo job de análise."""
    job_id: int
    message: str


class AnalysisResultSchema(BaseModel):
    """Schema para um único resultado de análise."""
    model_config = ConfigDict(from_attributes=True)
    date_analyzed: date
    predicted_atr: float


class AnalysisJobStatusResponse(BaseModel):
    """Resposta detalhada ao consultar o status de um job."""
    model_config = ConfigDict(from_attributes=True)
    job_id: int
    roi_id: Optional[int] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: List[AnalysisResultSchema] = Field(default_factory=list)
    error_message: Optional[str] = None
    child_jobs: List['AnalysisJobStatusResponse'] = Field(default_factory=list)
