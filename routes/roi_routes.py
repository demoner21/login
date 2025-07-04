from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import logging
from services.shapefile_service import ShapefileSplitterProcessor
from utils.jwt_utils import get_current_user
from utils.upload_utils import save_uploaded_files, cleanup_temp_files
from pydantic import BaseModel, Field

from database.roi_queries import (
    criar_propriedade_e_talhoes,
    listar_rois_usuario,
    obter_roi_por_id,
    atualizar_roi,
    deletar_roi,
    listar_talhoes_por_propriedade
)

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

def generate_roi_name(base_name: str, identifier: str, type_prefix: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    clean_base = Path(base_name).stem.replace(" ", "_")
    clean_identifier = str(identifier).replace(" ", "_").replace("/", "_")
    return f"{type_prefix}_{clean_base}_{clean_identifier}_{timestamp}"

def process_roi_data(roi_dict: dict) -> dict:
    processed = dict(roi_dict)
    if processed.get('geometria') and isinstance(processed['geometria'], str):
        try:
            processed['geometria'] = json.loads(processed['geometria'])
        except (json.JSONDecodeError, TypeError):
            processed['geometria'] = None
    if processed.get('metadata') and isinstance(processed['metadata'], str):
        try:
            processed['metadata'] = json.loads(processed['metadata'])
        except (json.JSONDecodeError, TypeError):
            processed['metadata'] = {}
    return processed

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
    response_model=HierarchicalUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Hierárquico] Upload de shapefile para criar Propriedades e Talhões",
    description="""
    Cria uma hierarquia de Regiões de Interesse (ROIs) a partir de um único shapefile.
    - **Requisito**: O shapefile deve conter colunas que identifiquem a propriedade e o talhão.
    - **Processamento**: Para cada propriedade única, uma ROI 'pai' é criada. Para cada talhão, uma ROI 'filha' é criada e vinculada à propriedade.
    - **CRS**: O sistema de referência final será sempre WGS84 (EPSG:4326).
    """
)
async def create_rois_from_shapefile_by_property(
    propriedade_col: str = Form(..., description="Nome da coluna no shapefile que identifica a 'Propriedade'. Ex: 'NM_PROP'"),
    talhao_col: str = Form(..., description="Nome da coluna no shapefile que identifica o 'Talhão'. Ex: 'ID_TALHAO'"),

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
        
        # Lógica de processamento HIERÁRQUICA
        processor = ShapefileSplitterProcessor()
        hierarchical_data = await processor.process(temp_dir, property_col=propriedade_col, plot_col=talhao_col)
        
        if not hierarchical_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhuma propriedade ou talhão válido encontrado para criar ROIs."
            )
        
        total_props_criadas = 0
        total_talhoes_criados = 0
        response_details = []

        for prop_info in hierarchical_data:
            prop_data_for_db = {
                "nome": generate_roi_name(shp.filename, prop_info['nome_propriedade'], "PROP"),
                "descricao": f"Propriedade '{prop_info['nome_propriedade']}' importada do arquivo {shp.filename}.",
                "nome_propriedade": prop_info['nome_propriedade'],
                "geometria": prop_info['geometria'],
                "metadata": prop_info['metadata']
            }

            plots_data_for_db = []
            for talhao_info in prop_info['talhoes']:
                plot_data = {
                    "nome": generate_roi_name(prop_info['nome_propriedade'], talhao_info['nome_talhao'], "TALHAO"),
                    "descricao": f"Talhão '{talhao_info['nome_talhao']}' da propriedade '{prop_info['nome_propriedade']}'.",
                    "nome_talhao": talhao_info['nome_talhao'],
                    "geometria": talhao_info['geometria'],
                    "metadata": talhao_info['metadata']
                }
                plots_data_for_db.append(plot_data)

            result = await criar_propriedade_e_talhoes(
                user_id=current_user['id'],
                property_data=prop_data_for_db,
                plots_data=plots_data_for_db,
                shp_filename=shp.filename
            )
            
            total_props_criadas += 1
            total_talhoes_criados += len(result['talhoes'])
            response_details.append({
                "propriedade": result['propriedade']['nome'],
                "roi_id_propriedade": result['propriedade']['roi_id'],
                "talhoes_criados": len(result['talhoes'])
            })

        return HierarchicalUploadResponse(
            mensagem="Processamento hierárquico concluído com sucesso.",
            propriedades_criadas=total_props_criadas,
            talhoes_criados=total_talhoes_criados,
            detalhes=response_details
        )
        
    except Exception as e:
        logger.error(f"Falha no endpoint de upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro inesperado: {str(e)}"
        )
    finally:
        if temp_dir:
            cleanup_temp_files(temp_dir)

@router.post("/processar-lote", summary="Processa um lote customizado de ROIs")
async def processar_lote_de_rois(
    request: LoteProcessamentoRequest,
    current_user: dict = Depends(get_current_user)
):
    from shapely.geometry import shape
    from shapely.ops import unary_union

    if not request.roi_ids:
        raise HTTPException(status_code=400, detail="A lista de IDs de ROI não pode ser vazia.")

    geometrias = []
    for roi_id in request.roi_ids:
        roi = await obter_roi_por_id(roi_id, current_user['id'])
        if not roi:
            raise HTTPException(status_code=404, detail=f"ROI com ID {roi_id} não encontrada ou não pertence ao usuário.")
        geometrias.append(shape(roi['geometria']))
    
    # Combina todas as geometrias em uma só
    geometria_unificada = unary_union(geometrias)
    
    # Aqui você chamaria o serviço do Earth Engine com a geometria_unificada
    # e retornaria o resultado (ex: URL de download, status do processamento, etc.)
    
    # Exemplo de resposta
    return {
        "message": "Processamento de lote iniciado com sucesso.",
        "total_rois": len(request.roi_ids),
        "geometria_combinada": mapping(geometria_unificada) # Retornando a geometria para debug
    }

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
            offset=offset,
            apenas_propriedades=True
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

@router.get("/propriedade/{propriedade_id}/talhoes", response_model=List[ROIResponse], summary="Lista os talhões de uma propriedade")
async def listar_talhoes_da_propriedade(
    propriedade_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Lista todas as ROIs do tipo 'TALHAO' que são filhas de uma ROI 'PROPRIEDADE' específica.
    """
    try:
        # Primeiro, verifica se a propriedade pai existe e pertence ao usuário
        propriedade = await obter_roi_por_id(propriedade_id, current_user['id'])
        if not propriedade or propriedade.get('tipo_roi') != 'PROPRIEDADE':
            raise HTTPException(status_code=404, detail="Propriedade não encontrada")

        # Busca os talhões filhos
        talhoes = await listar_talhoes_por_propriedade(propriedade_id, current_user['id'])
        return [process_roi_data(talhao) for talhao in talhoes]
    
    # --- INÍCIO DA CORREÇÃO ---
    except HTTPException as he:
        # Se for uma HTTPException (como a 404), apenas a levante novamente
        # para que o FastAPI a manipule corretamente.
        raise he
    except Exception as e:
        # Se for qualquer outra exceção inesperada, registre e levante um erro 500.
        logger.error(f"Erro inesperado ao listar talhões: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao listar talhões da propriedade"
        )