import json
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from utils.zip_creator import ZipCreator
from typing import Dict, List, Optional, Any

from fastapi import UploadFile
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

from utils.upload_utils import save_uploaded_files, cleanup_temp_files
from services.shapefile_service import ShapefileSplitterProcessor
from features.gee.service import gee_service
from features.jobs.queries import update_job_status
from uuid import UUID
from utils.text_normalizer import normalize_name
from . import queries, schemas
from database.session import with_db_connection, get_db_connection
import asyncpg

logger = logging.getLogger(__name__)


class ROIService:
    """
    Camada de serviço para manipular a lógica de negócio relacionada a
    Regiões de Interesse (ROIs).
    """

    def _generate_roi_name(self, base_name: str, identifier: str, type_prefix: str) -> str:
        """Gera um nome padronizado para a ROI."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        clean_base = Path(base_name).stem.replace(" ", "_")
        clean_identifier = str(identifier).replace(" ", "_").replace("/", "_")
        return f"{type_prefix}_{clean_base}_{clean_identifier}_{timestamp}"

    def _process_roi_data(self, roi_dict: dict) -> dict:
        """
        Processa os dados da ROI para garantir que campos JSON sejam dicionários
        e não strings.
        """
        if not isinstance(roi_dict, dict):
            return {}

        processed = dict(roi_dict)

        for key in ['geometria', 'metadata']:
            if processed.get(key) and isinstance(processed[key], str):
                try:
                    processed[key] = json.loads(processed[key])
                except (json.JSONDecodeError, TypeError):
                    processed[key] = {} if key == 'metadata' else None

        return processed

    async def process_shapefile_upload(self, *, conn: 'asyncpg.Connection', files: Dict[str, UploadFile], propriedade_col: str, talhao_col: str, user_id: int) -> Dict:
        """Orquestra o upload, processamento e criação de ROIs a partir de um shapefile."""
        temp_dir = None
        try:
            temp_dir = save_uploaded_files([f for f in files.values() if f])

            processor = ShapefileSplitterProcessor()
            hierarchical_data = await processor.process(temp_dir, property_col=propriedade_col, plot_col=talhao_col)

            if not hierarchical_data:
                raise ValueError(
                    "Nenhuma propriedade ou talhão válido encontrado para criar ROIs.")

            total_props_criadas = 0
            total_talhoes_criados = 0
            response_details = []

            for prop_info in hierarchical_data:
                prop_data_for_db = {
                    "nome": self._generate_roi_name(files['shp'].filename, prop_info['nome_propriedade'], "PROP"),
                    "descricao": f"Propriedade '{prop_info['nome_propriedade']}' importada do arquivo {files['shp'].filename}.",
                    "nome_propriedade": prop_info['nome_propriedade'],
                    "geometria": prop_info['geometria'],
                    "metadata": prop_info['metadata']
                }
                plots_data_for_db = [{
                    "nome": self._generate_roi_name(prop_info['nome_propriedade'], talhao_info['nome_talhao'], "TALHAO"),
                    "descricao": f"Talhão '{talhao_info['nome_talhao']}' da propriedade '{prop_info['nome_propriedade']}'.",
                    "nome_talhao": talhao_info['nome_talhao'],
                    "geometria": talhao_info['geometria'],
                    "metadata": talhao_info['metadata']
                } for talhao_info in prop_info['talhoes']]

                result = await queries.criar_propriedade_e_talhoes(
                    conn=conn,
                    user_id=user_id,
                    property_data=prop_data_for_db,
                    plots_data=plots_data_for_db,
                    shp_filename=files['shp'].filename
                )

                total_props_criadas += 1
                total_talhoes_criados += len(result['talhoes'])
                response_details.append({
                    "propriedade": result['propriedade']['nome'],
                    "roi_id_propriedade": result['propriedade']['roi_id'],
                    "talhoes_criados": len(result['talhoes'])
                })

            return {
                "mensagem": "Processamento hierárquico concluído com sucesso.",
                "propriedades_criadas": total_props_criadas,
                "talhoes_criados": total_talhoes_criados,
                "detalhes": response_details
            }
        finally:
            if temp_dir:
                cleanup_temp_files(temp_dir)

    async def process_batch_rois(self, *, roi_ids: List[int], user_id: int) -> Dict:
        """Combina as geometrias de uma lista de ROIs."""
        if not roi_ids:
            raise ValueError("A lista de IDs de ROI não pode ser vazia.")

        rois = await queries.listar_rois_por_ids_para_batch(user_id=user_id, roi_ids=roi_ids)
        if not rois:
            raise ValueError("Nenhuma ROI válida encontrada para os IDs fornecidos.")

        geometries = [shape(roi['geometria']) for roi in rois if roi.get('geometria')]
        if not geometries:
            raise ValueError("Nenhuma geometria válida encontrada nas ROIs selecionadas.")

        unified_geometry = unary_union(geometries)

        return {
            "total_rois": len(roi_ids),
            "geometria_combinada": mapping(unified_geometry)
        }

    async def get_user_rois(self, *, user_id: int, limit: int, offset: int, filtro_propriedade: Optional[str], filtro_variedade: Optional[str]) -> Dict:
        """Busca ROIs de um usuário, processa os dados e retorna."""
        result_db = await queries.listar_rois_usuario(
            user_id=user_id,
            limit=limit,
            offset=offset,
            filtro_propriedade=filtro_propriedade,
            filtro_variedade=filtro_variedade,
            apenas_propriedades=True
        )
        processed_rois = [self._process_roi_data(
            roi) for roi in result_db.get("rois", [])]
        return {"total": result_db.get("total", 0), "rois": processed_rois}

    async def get_available_properties(self, *, user_id: int) -> List[str]:
        """Busca a lista de propriedades únicas para um usuário."""
        return await queries.listar_propriedades_unicas(user_id=user_id)

    async def get_available_varieties(self, *, user_id: int) -> List[str]:
        """Busca a lista de variedades únicas para um usuário."""
        return await queries.listar_variedades_unicas(user_id=user_id)

    async def get_roi_by_id(self, *, roi_id: int, user_id: int) -> Optional[Dict]:
        """Busca uma única ROI e processa seus dados para garantir o formato correto."""
        roi = await queries.obter_roi_por_id(roi_id, user_id)
        if not roi:
            return None
        return self._process_roi_data(roi)

    async def update_roi(self, *, roi_id: int, user_id: int, update_data: schemas.ROICreate) -> Optional[Dict]:
        """Atualiza uma ROI e retorna os dados completos e processados."""
        update_dict = update_data.model_dump(exclude_unset=True)
        if not update_dict:
            raise ValueError("Nenhum dado fornecido para atualização.")

        updated = await queries.atualizar_roi(roi_id=roi_id, user_id=user_id, update_data=update_dict)
        if not updated:
            return None

        return await self.get_roi_by_id(roi_id=roi_id, user_id=user_id)

    async def delete_roi(self, *, roi_id: int, user_id: int) -> bool:
        """Verifica se a ROI existe e então a deleta."""
        roi_exists = await queries.obter_roi_por_id(roi_id, user_id)
        if not roi_exists:
            return False
        return await queries.deletar_roi(roi_id, user_id)

    async def get_plots_by_property(self, *, propriedade_id: int, user_id: int) -> List[Dict]:
        """Busca os talhões de uma propriedade, garantindo que a propriedade exista."""
        parent_roi = await queries.obter_roi_por_id(propriedade_id, user_id)
        if not parent_roi or parent_roi.get('tipo_roi') != 'PROPRIEDADE':
            raise ValueError(
                f"Propriedade com ID {propriedade_id} não encontrada.")

        talhoes = await queries.listar_talhoes_por_propriedade(propriedade_id, user_id)
        return [self._process_roi_data(t) for t in talhoes]
        
    # *** INÍCIO DA CORREÇÃO ***
    async def start_download_for_variety_in_property(
        self,
        *,
        job_id: UUID,
        user_id: int,
        propriedade_id: int,
        request_data: schemas.VarietyDownloadRequest,
        #batch_folder_name: str
    ) -> None:
        """
        Busca os talhões de uma variedade e delega o download para a função de lote principal.
        """
        logger.info(f"[Job {job_id}] Buscando talhões da variedade '{request_data.variedade}' na propriedade ID {propriedade_id}.")
        
        # Busca os IDs dos talhões que correspondem aos critérios
        talhoes = await queries.listar_talhoes_por_propriedade_e_variedade(
            user_id=user_id,
            propriedade_id=propriedade_id,
            variedade=request_data.variedade
        )
        
        if not talhoes:
            msg = "Nenhum talhão encontrado para os critérios de propriedade e variedade fornecidos."
            logger.warning(f"[Job {job_id}] {msg}")
            # Atualiza o job como falha se nada for encontrado
            await update_job_status(job_id=job_id, status='FAILED', message=msg)
            return

        roi_ids = [t['roi_id'] for t in talhoes]
        logger.info(f"[Job {job_id}] Encontrados {len(roi_ids)} talhões. Disparando download em lote.")

        # 2. DELEGUE para a função que já tem a lógica completa de job
        await self.start_batch_download_for_ids(
            job_id=job_id,
            user_id=user_id,
            roi_ids=roi_ids,
            start_date=request_data.start_date.isoformat(),
            end_date=request_data.end_date.isoformat(),
            max_cloud_percentage=request_data.max_cloud_percentage
        )

    async def start_batch_download_for_ids(
        self,
        *,
        job_id: UUID,
        user_id: int,
        roi_ids: List[int],
        start_date: str,
        end_date: str,
        bands: Optional[List[str]] = None,
        max_cloud_percentage: int = 5,
        #batch_folder_name: str
    ) -> None:
        logger.info(f"[Job {job_id}] Iniciando tarefa de download para IDs: {roi_ids}.")
        output_base_dir = Path(f"static/downloads/user_{user_id}/{job_id}")
        os.makedirs(output_base_dir, exist_ok=True)

        try:
            await update_job_status(job_id=job_id, status='PROCESSING', message='Iniciando download das imagens do GEE.')
        
            rois_to_process = await queries.listar_rois_por_ids_para_batch(
                user_id=user_id, roi_ids=roi_ids
            )
            if not rois_to_process:
                await update_job_status(job_id=job_id, status='FAILED', message='Nenhuma ROI válida foi encontrada para os IDs fornecidos.')
                return

            download_warnings = []
            total_files_downloaded_count = 0

            for roi_dict in rois_to_process:
                processed_roi = self._process_roi_data(roi_dict)
                roi_id = processed_roi['roi_id']
                roi_name = processed_roi.get('nome_talhao', f"ID {roi_id}")

                logger.info(f"Processando download para o talhão: {roi_name}")

                result = await gee_service.download_images_for_roi(
                    roi=processed_roi,
                    start_date=start_date,
                    end_date=end_date,
                    output_base_dir=output_base_dir,
                    bands_to_download=bands,
                    max_cloud_percentage=max_cloud_percentage
                )

                if result.get("status") == "warning":
                    warning_msg = f"Aviso para o Talhão '{roi_name}' (ID: {roi_id}): {result.get('message')}"
                    logger.warning(warning_msg)
                    download_warnings.append(warning_msg)
                elif result.get("status") == "success":
                    msg = result.get("message", "")
                    files_downloaded = int(msg.split(" ")[0]) if msg and msg.split(" ")[0].isdigit() else 0
                    total_files_downloaded_count += files_downloaded

            logger.info(f"[Job {job_id}] Fase de download do GEE concluída.")

            if total_files_downloaded_count == 0:
                error_message = "Processo concluído, mas nenhuma imagem foi encontrada para os filtros aplicados."
                logger.error(f"[Job {job_id}] {error_message}")
                await update_job_status(job_id=job_id, status='FAILED', message=error_message)
                return

            zip_creator = ZipCreator()
            zip_buffer = zip_creator.create_zip_from_directory(output_base_dir)
            zip_filename = output_base_dir / "download_completo.zip"
            with open(zip_filename, "wb") as f:
                f.write(zip_buffer.getvalue())
            logger.info(f"[Job {job_id}] Arquivo ZIP final salvo em: {zip_filename}")

            final_message = "Download concluído com sucesso."
            if download_warnings:
                final_message += f" {len(download_warnings)} talhões não tinham imagens disponíveis."

            await update_job_status(
                job_id=job_id,
                status='COMPLETED',
                message=final_message,
                result_path=str(zip_filename)
            )

        except Exception as e:
            error_message = f"Ocorreu um erro crítico durante o processamento: {e}"
            logger.error(f"[Job {job_id}] {error_message}", exc_info=True)
            await update_job_status(
                job_id=job_id,
                status='FAILED',
                message=error_message
            )

        finally:
            logger.info(f"Iniciando limpeza do diretório do job {job_id}.")
            for item_path in output_base_dir.iterdir():
                if item_path.name != "download_completo.zip":
                    try:
                        if item_path.is_dir():
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except Exception as e:
                        logger.error(f"Não foi possível remover o item temporário {item_path}: {e}")
            logger.info(f"Limpeza concluída.")


roi_service = ROIService()