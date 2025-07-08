from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from database.database import (
    get_user_by_email,
    verify_password,
    get_password_hash,
    inserir_usuario,
    verificar_email_existente,
    store_refresh_token,
    delete_user_refresh_tokens 
)
from utils.jwt_utils import (
    create_access_token,
    oauth2_scheme,
    get_current_user,
    create_refresh_token,
    Token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter(prefix="/auth", tags=["Auth"])

auth_logger = logging.getLogger('auth_routes')

class UserCreate(BaseModel):
    nome: str
    email: str
    senha: str
    confirmar_senha: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """
    Registra um novo usuário no sistema.
    """
    try:
        # Verificar se as senhas coincidem
        if user_data.senha != user_data.confirmar_senha:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="As senhas não coincidem"
            )

        # Verificar se o email já existe
        if await verificar_email_existente(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado"
            )

        # Inserir novo usuário
        await inserir_usuario(
            nome=user_data.nome,
            email=user_data.email,
            senha=user_data.senha,
            role="user"  # Papel padrão
        )

        return {"message": "Usuário registrado com sucesso"}

    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(f"Erro no registro: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar usuário"
        )

@router.post("/token", status_code=status.HTTP_204_NO_CONTENT)
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint para login de usuários.
    Define um cookie HttpOnly para o access token
    e outro para o refresh token.
    """
    auth_logger.info(f"Tentativa de login para: {form_data.username}")
    
    try:
        user = await get_user_by_email(form_data.username)
        
        if not user or not verify_password(form_data.password, user['senha']):
            auth_logger.warning(f"Falha na autenticação para: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas",
            )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['email']}, expires_delta=access_token_expires
        )

        # 2. Criar Refresh Token (longa duração)
        refresh_token = create_refresh_token(data={"sub": user['email']})

        # 3. Armazenar o hash do refresh token no DB
        await store_refresh_token(user_id=user['id'], token=refresh_token)

        # 4. Configurar cookies seguros
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite='lax',
            secure=True,
            path="/",
            max_age=int(access_token_expires.total_seconds())
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            samesite='lax',
            secure=True,
            path="/api/v1/auth/refresh",
            max_age=int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
        )

        auth_logger.info(f"Login bem-sucedido para: {user['email']}")
        
        # A função termina aqui, sem 'return'.
        # FastAPI enviará a resposta 204 com o cookie.
        return

    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(f"Erro no login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno no servidor"
        )

@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Retorna informações do usuário atual.
    """
    return current_user

@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(response: Response, refresh_token: Optional[str] = Cookie(None)):
    """
    Usa o refresh token (de um cookie HttpOnly) para gerar um novo access token.
    """
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token não encontrado")

    user = await get_user_by_refresh_token(token=refresh_token)
    if not user:
        # Se o token não for válido ou já tiver sido usado, nega o acesso
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido ou expirado")

    # Token é válido, gerar novos tokens (Rotação de Token)
    new_access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": user['email']}, expires_delta=new_access_token_expires
    )
    new_refresh_token = create_refresh_token(data={"sub": user['email']})
    
    await store_refresh_token(user_id=user['id'], token=new_refresh_token)

    response.set_cookie(
        key="access_token", value=new_access_token, httponly=True, samesite='lax', secure=True, path="/", max_age=int(new_access_token_expires.total_seconds())
    )
    response.set_cookie(
        key="refresh_token", value=new_refresh_token, httponly=True, samesite='lax', secure=True, path="/api/v1/auth/refresh", max_age=int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
    )
    return

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    """
    Faz logout do usuário, invalidando o refresh token no servidor e limpando os cookies.
    """
    user_id = current_user['id']
    await delete_user_refresh_tokens(user_id) # Remove do DB

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")
    
    auth_logger.info(f"Logout bem-sucedido para: {current_user['email']}")
    return