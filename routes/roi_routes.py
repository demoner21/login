from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import logging
from services.shapefile_service import ShapefileSplitterProcessor
from database.roi_queries import criar_roi, listar_rois_usuario, obter_roi_por_id, atualizar_roi, deletar_roi
from utils.jwt_utils import get_current_user
from utils.upload_utils import save_uploaded_files, cleanup_temp_files
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/roi",
    tags=["Regiões de Interesse"],
    responses={404: {"description": "Não encontrado"}}
)
logger = logging.getLogger(__name__)

# --- Modelos Pydantic ---

class ROIBase(BaseModel):
    nome: str
    descricao: Optional[str] = "ROI criada via upload de shapefile"
    geometria: Optional[Dict[str, Any]] = None
    tipo_origem: str
    status: Optional[str] = "ativo"
    nome_arquivo_original: Optional[str] = None
    metadata: Optional[Dict] = None

class ROIResponse(ROIBase):
    roi_id: int
    data_criacao: Optional[datetime] = None
    data_modificacao: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ShapefileSplitUploadResponse(BaseModel):
    rois_criadas: List[ROIResponse]
    arquivos_processados: List[str]
    total_rois: int
    mensagem: str

class ROICreate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None

VALID_STATUS_VALUES = ["ativo", "inativo", "processando", "erro"]


def process_roi_data(roi_dict: dict) -> dict:
    """Processa os dados da ROI para garantir o formato correto dos campos JSON"""
    processed = dict(roi_dict)
    
    # Lida com a geometria
    if processed.get('geometria') and isinstance(processed['geometria'], str):
        try:
            processed['geometria'] = json.loads(processed['geometria'])
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Erro ao decodificar geometria para ROI {processed.get('roi_id')}")
            processed['geometria'] = None
    
    # Lida com os metadados
    if processed.get('metadata') and isinstance(processed['metadata'], str):
        try:
            processed['metadata'] = json.loads(processed['metadata'])
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Erro ao decodificar metadata para ROI {processed.get('roi_id')}")
            processed['metadata'] = {}
    
    return processed


# --- Funções Auxiliares ---

def validate_shapefile_files(files: Dict[str, UploadFile]):
    """Valida os arquivos do shapefile antes do processamento"""
    errors = []
    
    required_files = ['shp', 'shx', 'dbf']
    for req in required_files:
        if req not in files or files[req] is None:
            errors.append(f"Arquivo .{req} é obrigatório")
    
    MAX_FILE_SIZE_MB = 20
    for file_type, file in files.items():
        if file is None:
            continue
            
        file_size = file.size / (1024 * 1024)  # MB
        if file_size > MAX_FILE_SIZE_MB:
            errors.append(f"Arquivo {file.filename} excede o tamanho máximo de {MAX_FILE_SIZE_MB}MB")
    
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors}
        )

def generate_roi_name(user_id: int, original_name: str, property_name: str) -> str:
    """Gera um nome padronizado para a ROI baseado na propriedade e no tempo."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = Path(original_name).stem.replace(" ", "_")
    clean_property = property_name.replace(" ", "_").replace("/", "_")
    return f"ROI_{user_id}_{clean_name}_{clean_property}_{timestamp}"

def process_roi_data(roi_dict: dict) -> dict:
    """Processa os dados da ROI para garantir o formato correto dos campos JSON"""
    processed = dict(roi_dict)
    
    # Lida com a geometria
    if processed.get('geometria') and isinstance(processed['geometria'], str):
        try:
            processed['geometria'] = json.loads(processed['geometria'])
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Erro ao decodificar geometria para ROI {processed.get('roi_id')}")
            processed['geometria'] = None
    
    # Lida com os metadados
    if processed.get('metadata') and isinstance(processed['metadata'], str):
        try:
            processed['metadata'] = json.loads(processed['metadata'])
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Erro ao decodificar metadata para ROI {processed.get('roi_id')}")
            processed['metadata'] = {}
    return processed

# --- Endpoints da API ---

@router.post(
    "/upload-shapefile-splitter", 
    response_model=ShapefileSplitUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de shapefile para criar ROIs por propriedade",
    description="""
    Cria múltiplas Regiões de Interesse (ROIs) a partir de um único shapefile, 
    agrupando as feições pelo campo 'Propriedad'.
    - **Arquivos obrigatórios**: .shp, .shx e .dbf
    - **Processamento**: Geometrias 3D são convertidas para 2D (removendo o eixo Z).
    - **Resultado**: Uma ROI é criada para cada valor único na coluna 'Propriedad'.
    - **CRS**: O sistema de referência final será WGS84 (EPSG:4326).
    """,
    responses={
        400: {"description": "Erro na validação dos arquivos ou dados"},
        500: {"description": "Erro interno no processamento"}
    }
)
async def create_rois_from_shapefile_by_property(
    descricao: str = Form(..., description="Descrição base para as ROIs a serem criadas"),
    shp: UploadFile = File(..., description="Arquivo principal .shp"),
    shx: UploadFile = File(..., description="Arquivo de índice .shx"),
    dbf: UploadFile = File(..., description="Arquivo de atributos .dbf"),
    prj: UploadFile = File(None, description="Arquivo de projeção .prj (opcional)"),
    cpg: UploadFile = File(None, description="Arquivo de codificação .cpg (opcional)"),
    current_user: dict = Depends(get_current_user)
):

    files = {'shp': shp, 'shx': shx, 'dbf': dbf, 'prj': prj, 'cpg': cpg}
    temp_dir = None
    try:
        temp_dir = save_uploaded_files([f for f in files.values() if f])
        logger.info(f"Arquivos do shapefile salvos em: {temp_dir}")
        
        processor = ShapefileSplitterProcessor()
        processing_results = await processor.process(temp_dir, group_by_column='Propriedad')
        # Ajustar para lidar com os diferentes casos de nome de dentro de um dataframe
        # Olha aqui
        
        if not processing_results:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhuma propriedade válida encontrada para criar ROIs."
            )
        
        logger.info(f"Shapefile dividido em {len(processing_results)} grupos (ROIs).")
        
        created_rois_list = []
        for result in processing_results:
            property_name = result['property_name']
            feature_collection = result['feature_collection']
            processing_metadata = result['metadata']

            # Gerar nome e preparar dados para a ROI
            roi_name = generate_roi_name(current_user['id'], files['shp'].filename, property_name)
            
            roi_data = {
                "nome": roi_name,
                "descricao": f"{descricao} - Propriedade: {property_name}",
                "geometria": feature_collection,
                "tipo_origem": "shapefile_split",
                "metadata": {
                    **processing_metadata,
                    "arquivos_originais": [f.filename for f in files.values() if f]
                },
                "nome_arquivo_original": files['shp'].filename,
                "status": "ativo"
            }

            created_roi_db = await criar_roi(
                user_id=current_user['id'],
                roi_data=roi_data
            )
            
            # 1. Processa o resultado do DB para converter strings em dicionários.
            processed_roi_db = process_roi_data(created_roi_db)
            
            created_rois_list.append(ROIResponse.model_validate(processed_roi_db))

        return ShapefileSplitUploadResponse(
            rois_criadas=created_rois_list,
            arquivos_processados=[f.filename for f in files.values() if f],
            total_rois=len(created_rois_list),
            mensagem=f"{len(created_rois_list)} ROIs criadas com sucesso a partir do shapefile."
        )
        
    except Exception as e:
        logger.error(f"Falha no endpoint de upload e divisão de shapefile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro inesperado: {str(e)}"
        )
    finally:
        if temp_dir:
            cleanup_temp_files(temp_dir)


@router.get("/status/options", summary="Lista os valores de status válidos")
async def get_status_options():
    """Lista os valores de status válidos para ROIs"""
    return {
        "status_options": VALID_STATUS_VALUES,
        "description": "Valores válidos para o campo status de uma ROI"
    }

@router.get("/", response_model=List[ROIResponse], summary="Lista as ROIs do usuário")
async def listar_minhas_rois(
    current_user: dict = Depends(get_current_user),
    limit: int = 10,
    offset: int = 0
):
    """Lista todas as ROIs do usuário com paginação"""
    try:
        rois = await listar_rois_usuario(
            user_id=current_user['id'],
            limit=limit,
            offset=offset
        )
        
        return [process_roi_data(roi) for roi in rois]
        
    except Exception as e:
        logger.error(f"Erro ao listar ROIs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar regiões de interesse"
        )

@router.get("/{roi_id}", response_model=ROIResponse, summary="Obtém uma ROI específica")
async def obter_roi(
    roi_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Obtém uma ROI específica do usuário, verificando a propriedade"""
    try:
        roi = await obter_roi_por_id(roi_id, current_user['id'])
        if not roi:
            raise HTTPException(status_code=404, detail="ROI não encontrada")
        
        processed_roi = process_roi_data(roi)
        return ROIResponse.model_validate(processed_roi)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao obter ROI: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter região de interesse"
        )

@router.put(
    "/{roi_id}", 
    response_model=ROIResponse,
    summary="Atualiza uma ROI",
    description="Atualiza os campos 'nome' e 'descrição' de uma Região de Interesse."
)
async def atualizar_roi_route(
    roi_id: int,
    update_data: ROICreate,
    current_user: dict = Depends(get_current_user)
):
    """Atualiza metadados de uma ROI (nome e descrição)"""
    try:
        # Verifica se a ROI existe e pertence ao usuário
        if not await obter_roi_por_id(roi_id, current_user['id']):
            raise HTTPException(status_code=404, detail="ROI não encontrada")
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        updated = await atualizar_roi(
            roi_id=roi_id,
            user_id=current_user['id'],
            update_data=update_dict
        )
        
        # Busca a ROI atualizada para retornar todos os dados no modelo de resposta
        updated_roi = await obter_roi_por_id(roi_id, current_user['id'])
        if not updated_roi:
            raise HTTPException(status_code=404, detail="ROI não encontrada após atualização")
        
        processed_roi = process_roi_data(updated_roi)
        return ROIResponse.model_validate(processed_roi)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao atualizar ROI: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/{roi_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove uma ROI")
async def deletar_roi_route(
    roi_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Remove uma ROI do banco de dados, verificando a propriedade"""
    try:
        # Verifica se a ROI existe e pertence ao usuário
        if not await obter_roi_por_id(roi_id, current_user['id']):
            raise HTTPException(status_code=404, detail="ROI não encontrada")
        
        deleted = await deletar_roi(roi_id, current_user['id'])
        if not deleted:
            # Caso raro, mas para consistência
            raise HTTPException(status_code=404, detail="ROI não pôde ser deletada ou não encontrada")

        return None # Retorna 204 No Content em caso de sucesso

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao deletar ROI: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover região de interesse"
        )