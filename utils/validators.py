from datetime import datetime
from fastapi import HTTPException

def validate_date_range(start_date: str, end_date: str):
    """
    Valida se a data de início é anterior ou igual à data de término.
    Ideal para ser usada como dependência ou no início de um endpoint.
    """
    if datetime.strptime(start_date, "%Y-%m-%d") > datetime.strptime(end_date, "%Y-%m-%d"):
        raise HTTPException(
            status_code=422,
            detail="A data de início não pode ser maior que a data de término."
        )

def pydantic_date_range_validator(cls, v):
    """
    Validador no estilo Pydantic para ser usado dentro de schemas.
    """
    if not isinstance(v, list) or len(v) != 2:
        raise ValueError('Forneça exatamente duas datas (início e fim)')
    
    try:
        start_date = datetime.strptime(v[0], '%Y-%m-%d')
        end_date = datetime.strptime(v[1], '%Y-%m-%d')
        if end_date < start_date:
            raise ValueError('A data final deve ser posterior à data inicial')
        return v
    except (ValueError, TypeError):
        raise ValueError('Use o formato YYYY-MM-DD para as datas')