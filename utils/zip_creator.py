import os
import zipfile
import logging
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

class ZipCreator:
    def create_zip_from_directory(self, source_dir: Path) -> BytesIO:
        """
        Cria um arquivo ZIP em memória a partir do conteúdo de um diretório específico.

        Args:
            source_dir: O caminho (objeto Path) do diretório a ser compactado.

        Returns:
            BytesIO: Buffer contendo o arquivo ZIP.
        """
        zip_buffer = BytesIO()
        logger.info(f"Iniciando a criação do arquivo ZIP para o diretório: {source_dir}")

        try:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Percorre apenas o diretório de origem especificado
                for root, _, files in os.walk(source_dir):
                    for file in files:
                        # Adiciona apenas arquivos .tif
                        if file.endswith(".tif"):
                            file_path = Path(root) / file
                            # Escreve o arquivo no ZIP com um caminho relativo
                            zip_file.write(
                                file_path,
                                arcname=file_path.relative_to(source_dir)
                            )
            
            zip_buffer.seek(0)
            logger.info("Arquivo ZIP criado em memória com sucesso.")
            return zip_buffer

        except Exception as e:
            logger.error(f"Erro ao criar o arquivo ZIP: {e}", exc_info=True)
            raise