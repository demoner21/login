import re
import unicodedata
from typing import Union, List, Dict, Any
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

class NameNormalizer:
    """
    Classe para normalização de nomes e textos com tratamento de encoding problems
    e padronização de formatos.
    """
    
    CHAR_CORRECTIONS = {
        "Ã§": "ç", "Ã£": "ã", "Ã¢": "â", "Ã©": "é", "Ãª": "ê",
        "Ã³": "ó", "Ã´": "ô", "Ãµ": "õ", "Ã¡": "á", "Ã­": "í",
        "Ãº": "ú", "Ã": "à", "Ã»": "û", "Ã¤": "ä", "Ã¶": "ö",
        "Ã¼": "ü", "Ã¿": "ÿ", "Ã®": "î", "Ã¯": "ï", "Ãa": "ía",
        "ÃƒÂ¡": "á", "ÃƒÂ¢": "â", "ÃƒÂ£": "ã", "ÃƒÂ§": "ç",
        "ÃƒÂ©": "é", "ÃƒÂª": "ê", "ÃƒÂ­": "í", "ÃƒÂ³": "ó",
        "ÃƒÂ´": "ô", "ÃƒÂµ": "õ", "ÃƒÂº": "ú",
        "â€“": "-", "â€”": "-", "â€¢": "-", "â€¦": "...",
        "â€˜": "'", "â€™": "'", "â€œ": '"', "â€": '"',
    }

    # Palavras que devem permanecer em minúsculas em nomes próprios
    LOWERCASE_WORDS = {
        'de', 'do', 'da', 'dos', 'das', 'e', 'em', 'na', 'no', 
        'nas', 'nos', 'por', 'para', 'com', 'à', 'a', 'o', 'as', 'os'
    }

    MULTIPLE_SPACES = re.compile(r'\s+')
    SPECIAL_CHARS = re.compile(r'[^\w\s-]', re.UNICODE)
    LEADING_TRAILING_DASHES = re.compile(r'^-|-$')
    ENCODINGS = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

    @classmethod
    def normalize(cls, text: Union[str, bytes], case: str = 'title') -> str:
        """
        Normaliza um texto aplicando correções de encoding, removendo caracteres especiais
        e padronizando a formatação.
        
        Args:
            text: Texto a ser normalizado (pode ser string ou bytes)
            case: Formato de capitalização ('lower', 'upper', 'title', 'keep')
            
        Returns:
            str: Texto normalizado
        """
        if not text:
            return ''
            
        # Se for bytes, tentar decodificar
        if isinstance(text, bytes):
            text = cls._decode_bytes(text)
        
        text = cls._fix_encoding_issues(text) # Aplicar correções de caracteres
        text = unicodedata.normalize('NFKC', text) # Normalizar caracteres Unicode (NFKC: compatibilidade + composição)
        text = cls.SPECIAL_CHARS.sub('', text) # Remover caracteres especiais (exceto espaços e hífens)
        text = cls.MULTIPLE_SPACES.sub(' ', text).strip() # Substituir múltiplos espaços por um único        
        text = cls._apply_case(text, case) # Aplicar formatação de caso
        
        return text

    @classmethod
    @lru_cache(maxsize=1000)
    def _fix_encoding_issues(cls, text: str) -> str:
        """Corrige problemas de encoding em cascata com cache para performance."""
        original_text = text
        for wrong, right in cls.CHAR_CORRECTIONS.items():
            text = text.replace(wrong, right)
        
        if text != original_text:
            logger.debug(f"Corrigido encoding: '{original_text}' -> '{text}'")
        
        return text

    @classmethod
    def _decode_bytes(cls, byte_data: bytes) -> str:
        """Tenta decodificar bytes usando diferentes encodings."""
        for encoding in cls.ENCODINGS:
            try:
                return byte_data.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        logger.warning(f"Não foi possível decodificar bytes com encodings conhecidos. Usando replace.")
        return byte_data.decode('utf-8', errors='replace')

    @classmethod
    def _apply_case(cls, text: str, case: str) -> str:
        """Aplica a formatação de capitalização especificada."""
        case = case.lower()
        if case == 'lower':
            return text.lower()
        elif case == 'upper':
            return text.upper()
        elif case == 'title':
            words = text.split()
            if not words:
                return text
            # Capitaliza a primeira palavra
            result = [words[0].capitalize()]
            # Processa as palavras restantes
            for word in words[1:]:
                if word.lower() in cls.LOWERCASE_WORDS:
                    result.append(word.lower())
                else:
                    result.append(word.capitalize())
            return ' '.join(result)
        elif case == 'sentence':
            return text.capitalize()
        return text  # 'keep' ou inválido - mantém como está

    @classmethod
    def normalize_dict_keys(cls, data: Dict[str, Any], case: str = 'lower') -> Dict[str, Any]:
        """
        Normaliza as chaves de um dicionário aplicando a normalização de texto.
        
        Args:
            data: Dicionário com chaves a serem normalizadas
            case: Formato de capitalização para as chaves
            
        Returns:
            Dict: Novo dicionário com chaves normalizadas
        """
        return {cls.normalize(key, case): value for key, value in data.items()}

    @classmethod
    def normalize_list(cls, items: List[Union[str, bytes]], case: str = 'title') -> List[str]:
        """
        Normaliza uma lista de textos.
        
        Args:
            items: Lista de textos a serem normalizados
            case: Formato de capitalização
            
        Returns:
            List[str]: Lista com textos normalizados
        """
        return [cls.normalize(item, case) for item in items]


# Funções de conveniência para uso rápido
def normalize_name(name: Union[str, bytes], case: str = 'title') -> str:
    """Normaliza um nome próprio aplicando correções de encoding e formatação."""
    return NameNormalizer.normalize(name, case)

def normalize_text(text: Union[str, bytes], case: str = 'keep') -> str:
    """Normaliza um texto genérico mantendo a capitalização original por padrão."""
    return NameNormalizer.normalize(text, case)

def normalize_dict_keys(data: Dict[str, Any], case: str = 'lower') -> Dict[str, Any]:
    """Normaliza as chaves de um dicionário."""
    return NameNormalizer.normalize_dict_keys(data, case)