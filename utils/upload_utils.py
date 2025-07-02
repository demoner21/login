import tempfile
from pathlib import Path
import shutil
from typing import List
from fastapi import UploadFile
import logging

logger = logging.getLogger(__name__)

def save_uploaded_files(files: List[UploadFile]) -> Path:
    """
    Salva arquivos de upload em um diretório temporário SEGURO,
    fora da pasta do projeto, para evitar conflitos com o reloader do servidor.
    """
    # Cria um diretório temporário no local padrão do sistema (ex: /tmp)
    temp_dir = Path(tempfile.mkdtemp(prefix="shapefile_upload_"))
    logger.info(f"Diretório temporário criado em: {temp_dir}")
    
    try:
        for file in files:
            file_path = temp_dir / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        return temp_dir
    except Exception as e:
        logger.error(f"Erro ao salvar arquivos em {temp_dir}: {e}")
        # Limpa o diretório em caso de erro
        cleanup_temp_files(temp_dir)
        raise

def cleanup_temp_files(temp_dir: Path):
    """Remove o diretório temporário e todo o seu conteúdo."""
    if temp_dir and temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Diretório temporário {temp_dir} removido com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao remover diretório temporário {temp_dir}: {e}")