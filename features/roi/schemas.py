from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, date


class ROIBase(BaseModel):
    nome: str
    descricao: Optional[str] = "ROI criada via upload de shapefile"
    geometria: Optional[Dict[str, Any]] = None
    tipo_origem: str
    status: Optional[str] = "ativo"
    nome_arquivo_original: Optional[str] = None
    metadata: Optional[Dict] = None
    tipo_roi: Optional[str] = None
    roi_pai_id: Optional[int] = None
    nome_propriedade: Optional[str] = None
    nome_talhao: Optional[str] = None


class ROIResponse(ROIBase):
    roi_id: int
    data_criacao: Optional[datetime] = None
    data_modificacao: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HierarchicalUploadResponse(BaseModel):
    mensagem: str
    propriedades_criadas: int
    talhoes_criados: int
    detalhes: List[Dict]


class ROICreate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None


class LoteProcessamentoRequest(BaseModel):
    roi_ids: List[int]


class ROIListResponse(BaseModel):
    total: int
    rois: List[ROIResponse]


class DownloadRequest(BaseModel):
    start_date: date = Field(
        ..., description="Data de início (YYYY-MM-DD) para a busca de imagens.")
    end_date: date = Field(...,
                           description="Data de fim (YYYY-MM-DD) para a busca de imagens.")
    scale: Optional[int] = Field(10, description="Escala da imagem em metros.")


class VarietyDownloadResult(BaseModel):
    roi_id: int
    nome_talhao: str
    download_url: str
    status: str
    error_message: Optional[str] = None

class BatchDownloadRequest(BaseModel):
    roi_ids: List[int] = Field(..., description="Lista de IDs das ROIs (talhões) a serem processadas.")
    start_date: date = Field(..., description="Data de início (YYYY-MM-DD) para a busca de imagens.")
    end_date: date = Field(..., description="Data de fim (YYYY-MM-DD) para a busca de imagens.")
    bands: Optional[List[str]] = Field(
        None,
        description="Lista opcional de bandas para download. Se omitido, baixa todas."
    )

class BatchDownloadResponse(BaseModel):
    message: str
    task_details: Dict
    