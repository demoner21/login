from pydantic import BaseModel, Field, ConfigDict
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
    model_config = ConfigDict(from_attributes=True)
    roi_id: int
    data_criacao: Optional[datetime] = None
    data_modificacao: Optional[datetime] = None


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


class VarietyDownloadRequest(BaseModel):
    variedade: str = Field(..., description="Nome da variedade para download.")
    start_date: date = Field(..., description="Data de início (YYYY-MM-DD).")
    end_date: date = Field(..., description="Data de fim (YYYY-MM-DD).")
    max_cloud_percentage: Optional[int] = Field(
        5, ge=0, le=100, description="Percentual máximo de nuvens (0-100)."
    )


class BatchDownloadRequest(BaseModel):
    roi_ids: List[int] = Field(
        ..., description="Lista de IDs das ROIs (talhões) a serem processadas.")
    start_date: date = Field(
        ..., description="Data de início (YYYY-MM-DD) para a busca de imagens.")
    end_date: date = Field(...,
                           description="Data de fim (YYYY-MM-DD) para a busca de imagens.")
    bands: Optional[List[str]] = Field(
        None,
        description="Lista opcional de bandas para download. Se omitido, baixa todas."
    ),
    max_cloud_percentage: Optional[int] = Field(
        5,
        ge=0,
        le=100,
        description="Percentual máximo de nuvens permitido (0-100)."
    )


class BatchDownloadResponse(BaseModel):
    message: str
    task_details: Dict

class TalhaoSimplesResponse(BaseModel):
    """Schema simplificado para listar talhões em agrupamentos."""
    model_config = ConfigDict(from_attributes=False)
    
    roi_id: int 
    nome_talhao: str
    area_ha: Optional[float] = None
    variedade: Optional[str] = None
    
class VariedadeGroupingResponse(BaseModel):
    """Agrupamento de talhões por nome de variedade."""
    variedade_nome: str
    talhoes: List[TalhaoSimplesResponse]
    
class PropriedadeGroupingResponse(BaseModel):
    """Resposta hierárquica completa: Propriedade -> Variedade -> Talhão."""
    propriedade_id: int
    propriedade_nome: str