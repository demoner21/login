import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import UploadFile
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

from utils.upload_utils import save_uploaded_files, cleanup_temp_files
from services.shapefile_service import ShapefileSplitterProcessor
# from services.earth_engine import gee_service
from . import queries, schemas
from .schemas import DownloadRequest


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

    async def process_shapefile_upload(self, *, files: Dict[str, UploadFile], propriedade_col: str, talhao_col: str, user_id: int) -> Dict:
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

        geometries = []
        for roi_id in roi_ids:
            roi = await self.get_roi_by_id(roi_id=roi_id, user_id=user_id)
            if not roi or not roi.get('geometria'):
                raise ValueError(
                    f"ROI com ID {roi_id} não encontrada ou não possui geometria válida.")
            geometries.append(shape(roi['geometria']))

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

    async def get_gee_download_url(self, *, roi_id: int, user_id: int, request_data: schemas.DownloadRequest) -> Dict:
        """Gera uma URL de download do GEE para uma única ROI."""
        roi = await self.get_roi_by_id(roi_id=roi_id, user_id=user_id)
        if not roi or not roi.get('geometria'):
            raise ValueError(
                "ROI não encontrada ou não possui geometria válida.")

        geometria_para_gee = roi['geometria']
        if geometria_para_gee.get('type') == 'FeatureCollection':
            features = geometria_para_gee.get('features', [])
            if not features:
                raise ValueError(
                    "FeatureCollection da propriedade está vazia.")
            geometrias_dos_talhoes = [shape(f['geometry']) for f in features]
            geometria_unificada = unary_union(geometrias_dos_talhoes)
            geometria_para_gee = mapping(geometria_unificada)

        download_url = gee_service.get_download_url(
            geometry=geometria_para_gee,
            start_date=request_data.start_date,
            end_date=request_data.end_date,
            scale=request_data.scale
        )

        return {
            "message": "URL de download gerada com sucesso.",
            "roi_id": roi_id,
            "roi_name": roi.get('nome'),
            "download_url": download_url
        }


# Instância única do serviço para ser usada pelo roteador e por outros serviços
roi_service = ROIService()
