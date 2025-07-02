import ee
import os
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

load_dotenv()

def initialize_earth_engine(json_key_path=os.getenv('EE_JSON_KEY_PATH'), 
                          service_account_email=os.getenv('DEFAULT_SERVICE_ACCOUNT')):
    """
    Inicializa o Earth Engine com conta de serviço
    
    Args:
        json_key_path (str): Caminho para o arquivo JSON da chave
        service_account_email (str): Email da conta de serviço
    """
    try:
        if not os.path.exists(json_key_path):
            raise FileNotFoundError(f"Arquivo de chave não encontrado: {json_key_path}")

        credentials = service_account.Credentials.from_service_account_file(
            json_key_path,
            scopes=['https://www.googleapis.com/auth/earthengine']
        )
        
        credentials = credentials.with_subject(service_account_email)
        
        ee.Initialize(credentials)
        
        logger.info("Earth Engine inicializado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Falha na inicialização do Earth Engine: {str(e)}")
        raise RuntimeError("Erro na inicialização do Earth Engine") from e