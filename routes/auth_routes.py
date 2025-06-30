from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from database.database import (
    get_user_by_email,
    verify_password,
    get_password_hash,
    inserir_usuario,
    verificar_email_existente
)
from utils.jwt_utils import (
    create_access_token,
    oauth2_scheme,
    get_current_user,
    Token
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

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint para login de usuários.
    Retorna um token JWT para autenticação.
    """
    auth_logger.info(f"Tentativa de login para: {form_data.username}")
    
    try:
        # Buscar usuário no banco de dados
        user = await get_user_by_email(form_data.username)
        
        if not user:
            auth_logger.warning(f"Usuário não encontrado: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar senha
        if not verify_password(form_data.password, user['senha']):
            auth_logger.warning("Senha incorreta")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Gerar token de acesso
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user['email']},
            expires_delta=access_token_expires
        )

        auth_logger.info(f"Login bem-sucedido para: {user['email']}")
        return {"access_token": access_token, "token_type": "bearer"}

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