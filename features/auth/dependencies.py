from typing import Optional
from fastapi import Depends, HTTPException, status, Cookie
from jose import JWTError, jwt

from config import settings
from ..users.queries import get_user_by_email
from .schemas import TokenData


async def get_current_user(access_token: Optional[str] = Cookie(None)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado"
        )
    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = await get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user
