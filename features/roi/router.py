import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query, BackgroundTasks
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from fastapi.responses import FileResponse
from . import schemas
from .service import roi_service
from ..auth.dependencies import get_current_user
from utils.validators import validate_date_range

# O prefixo foi removido daqui para ser gerenciado no main.py, tornando o router mais reutilizável.
router = APIRouter(
    tags=["Regiões de Interesse (ROI)"],
    responses={404: {"description": "Não encontrado"}}
)
logger = logging.getLogger(__name__)
VALID_STATUS_VALUES = ["ativo", "inativo", "processando", "erro"]


@router.post(
    "/upload-shapefile-splitter",
    response_model=schemas.HierarchicalUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Hierárquico] Upload de shapefile"
)
async def create_rois_from_shapefile_by_property(
    propriedade_col: str = Form(...,
                                description="Coluna que identifica a 'Propriedade'."),
    talhao_col: str = Form(...,
                           description="Coluna que identifica o 'Talhão'."),
    shp: UploadFile = File(...), shx: UploadFile = File(...), dbf: UploadFile = File(...),
    prj: UploadFile = File(None), cpg: UploadFile = File(None),
    current_user: dict = Depends(get_current_user)
):
    """Cria uma hierarquia de ROIs a partir de um único shapefile."""
    files = {'shp': shp, 'shx': shx, 'dbf': dbf, 'prj': prj, 'cpg': cpg}
    try:
        # LÓGICA MOVIDA PARA O SERVIÇO
        # CORREÇÃO: Passando user_id em vez do objeto current_user inteiro.
        return await roi_service.process_shapefile_upload(
            files=files,
            propriedade_col=propriedade_col,
            talhao_col=talhao_col,
            user_id=current_user['id']
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Falha no endpoint de upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro inesperado no upload.")


@router.post("/processar-lote", summary="Processa um lote customizado de ROIs")
async def processar_lote_de_rois(
    request: schemas.LoteProcessamentoRequest,
    current_user: dict = Depends(get_current_user)
):
    """Recebe uma lista de IDs de ROI e combina suas geometrias."""
    try:
        # LÓGICA MOVIDA PARA O SERVIÇO
        result = await roi_service.process_batch_rois(
            roi_ids=request.roi_ids,
            user_id=current_user['id']
        )
        return {"message": "Processamento de lote concluído com sucesso.", **result}
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Falha ao processar lote: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao processar o lote.")


@router.get("/status/options", summary="Lista os valores de status válidos")
async def get_status_options():
    """Lista os valores de status válidos para ROIs."""
    return {"status_options": VALID_STATUS_VALUES}


@router.get("/", response_model=schemas.ROIListResponse, summary="Lista as ROIs do usuário")
async def listar_minhas_rois(
    current_user: dict = Depends(get_current_user), limit: int = 10, offset: int = 0,
    propriedade: Optional[str] = Query(None), variedade: Optional[str] = Query(None)
):
    """Lista todas as ROIs do usuário com paginação, filtros e contagem total."""
    # LÓGICA MOVIDA PARA O SERVIÇO
    return await roi_service.get_user_rois(
        user_id=current_user['id'], limit=limit, offset=offset,
        filtro_propriedade=propriedade, filtro_variedade=variedade
    )


@router.get("/propriedades-disponiveis", response_model=List[str], summary="Lista propriedades únicas")
async def get_propriedades_disponiveis(current_user: dict = Depends(get_current_user)):
    """Obtém uma lista de todas as propriedades únicas de um usuário."""
    # LÓGICA MOVIDA PARA O SERVIÇO
    return await roi_service.get_available_properties(user_id=current_user['id'])


@router.get("/variedades-disponiveis", response_model=List[str], summary="Lista variedades únicas")
async def get_variedades_disponiveis(current_user: dict = Depends(get_current_user)):
    """Obtém uma lista de todas as variedades únicas associadas aos talhões de um usuário."""
    # LÓGICA MOVIDA PARA O SERVIÇO
    return await roi_service.get_available_varieties(user_id=current_user['id'])


@router.get("/{roi_id}", response_model=schemas.ROIResponse, summary="Obtém uma ROI específica")
async def obter_roi(roi_id: int, current_user: dict = Depends(get_current_user)):
    """Obtém uma ROI específica do usuário, verificando a propriedade."""
    # LÓGICA MOVIDA PARA O SERVIÇO
    roi = await roi_service.get_roi_by_id(roi_id=roi_id, user_id=current_user['id'])
    if not roi:
        raise HTTPException(status_code=404, detail="ROI não encontrada")
    return roi


@router.put("/{roi_id}", response_model=schemas.ROIResponse, summary="Atualiza uma ROI")
async def atualizar_roi_route(roi_id: int, update_data: schemas.ROICreate, current_user: dict = Depends(get_current_user)):
    """Atualiza metadados de uma ROI (nome e descrição)."""
    # LÓGICA MOVIDA PARA O SERVIÇO
    updated_roi = await roi_service.update_roi(
        roi_id=roi_id, user_id=current_user['id'], update_data=update_data
    )
    if not updated_roi:
        raise HTTPException(
            status_code=404, detail="ROI não encontrada ou falha na atualização")
    return updated_roi


@router.delete("/{roi_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove uma ROI")
async def deletar_roi_route(roi_id: int, current_user: dict = Depends(get_current_user)):
    """Remove uma ROI do banco de dados, verificando a propriedade."""
    # LÓGICA MOVIDA PARA O SERVIÇO
    deleted = await roi_service.delete_roi(roi_id=roi_id, user_id=current_user['id'])
    if not deleted:
        raise HTTPException(
            status_code=404, detail="ROI não encontrada ou não pôde ser deletada")
    return None


@router.get("/propriedade/{propriedade_id}/talhoes", response_model=List[schemas.ROIResponse], summary="Lista talhões de uma propriedade")
async def listar_talhoes_da_propriedade(propriedade_id: int, current_user: dict = Depends(get_current_user)):
    """Lista todas as ROIs 'TALHAO' que são filhas de uma 'PROPRIEDADE' específica."""
    try:
        # LÓGICA MOVIDA PARA O SERVIÇO
        return await roi_service.get_plots_by_property(
            propriedade_id=propriedade_id, user_id=current_user['id']
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@router.post("/{roi_id}/download", response_model=dict, summary="[GEE] Requisita download para ROI")
async def request_gee_download(
    roi_id: int, request_data: schemas.DownloadRequest, current_user: dict = Depends(get_current_user)
):
    """Inicia um processo no GEE para gerar e obter uma URL de download de imagem para a ROI."""
    try:
        # A chamada ao serviço já estava correta aqui
        return await roi_service.get_gee_download_url(
            roi_id=roi_id, user_id=current_user['id'], request_data=request_data
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Falha no GEE para ROI {roi_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Erro ao processar a requisição no GEE.")

@router.post(
    "/batch-download",
    response_model=schemas.BatchDownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[GEE] Inicia download em lote para ROIs selecionadas"
)
async def download_images_for_selected_rois(
    background_tasks: BackgroundTasks,
    request_data: schemas.BatchDownloadRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Inicia um processo em segundo plano para baixar imagens do Sentinel-2
    para uma lista específica de IDs de ROI (talhões).

    A resposta é imediata, e o processo continua no servidor.
    """
    validate_date_range(
        request_data.start_date.isoformat(),
        request_data.end_date.isoformat()
        )

    try:
        user_id = current_user['id']
        if not request_data.roi_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A lista de IDs de ROI não pode ser vazia."
            )

        logger.info(f"Requisição de download em lote para {len(request_data.roi_ids)} ROIs recebida.")

        batch_folder_name = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        future_zip_path = f"static/downloads/user_{user_id}/{batch_folder_name}/download_completo.zip"
        
        # Adiciona a nova função de serviço à fila de tarefas
        background_tasks.add_task(
            roi_service.start_batch_download_for_ids, # Nova função que criaremos a seguir
            user_id=user_id,
            roi_ids=request_data.roi_ids,
            start_date=request_data.start_date.isoformat(),
            end_date=request_data.end_date.isoformat(),
            bands=request_data.bands
        )

        return {
        "message": "A tarefa foi iniciada. O arquivo ZIP estará disponível em breve.",
        "task_details": {
            "download_link": f"/api/v1/roi/download-zip/{batch_folder_name}"
        }
    }
    except Exception as e:
        logger.error(f"Falha ao iniciar a tarefa de download em lote: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível iniciar a tarefa de download."
        )

@router.get(
    "/download-zip/{batch_folder_name}",
    response_class=FileResponse,
    summary="Baixa um arquivo ZIP de um lote processado"
)
async def get_zip_file(
    batch_folder_name: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user['id']
    file_path = Path(f"static/downloads/user_{user_id}/{batch_folder_name}/download_completo.zip")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou ainda não processado.")

    return FileResponse(
        path=file_path,
        media_type='application/zip',
        filename=f"{batch_folder_name}.zip"
    )
