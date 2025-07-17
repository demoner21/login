import logging
from fastapi import APIRouter, Depends, HTTPException, status, Response
from . import queries, schemas
from ..auth.dependencies import get_current_user
from ..users.queries import delete_user_refresh_tokens

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/me",
    response_model=schemas.UserResponse,
    summary="Retorna os dados do usuário autenticado"
)
async def get_logged_in_user_data(current_user: dict = Depends(get_current_user)):
    """Endpoint para que o frontend possa buscar os dados do usuário logado."""
    return current_user

@router.put(
    "/me",
    response_model=schemas.UserResponse,
    summary="Atualiza os dados do usuário autenticado"
)
async def update_user_data(
    update_data: schemas.UserUpdate,
    response: Response,
    current_user: dict = Depends(get_current_user)
):
    """
    Permite que um usuário logado atualize seu nome e/ou email.
    Se o email for alterado, o usuário será deslogado para reautenticação.
    """
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum dado fornecido para atualização."
        )

    try:
        updated_user = await queries.atualizar_dados_usuario(
            user_id=current_user['id'],
            update_data=update_dict
        )

        # Se o email foi alterado, o token JWT atual se torna inválido.
        # O usuário deve ser forçado a fazer login novamente.
        if "email" in update_dict and updated_user:
            # Invalida os refresh tokens no backend
            await delete_user_refresh_tokens(user_id=current_user['id'])
            # Limpa os cookies de autenticação no navegador
            response.delete_cookie("access_token", path="/")
            response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")
            logger.info(f"Usuário {current_user['email']} teve o email alterado para {updated_user['email']} e foi deslogado.")

        return updated_user

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao atualizar dados do usuário {current_user['email']}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao atualizar dados.")


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Atualiza a senha do usuário autenticado"
)
async def update_password(
    update_data: schemas.PasswordUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Permite que um usuário logado atualize sua própria senha.
    É necessário fornecer a senha atual e a nova senha.
    """
    if update_data.senha_atual == update_data.nova_senha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha não pode ser igual à senha atual."
        )
    try:
        await queries.atualizar_senha_usuario_autenticado(
            user_id=current_user['id'],
            senha_atual=update_data.senha_atual,
            nova_senha=update_data.nova_senha
        )
        # Retorna 204 No Content em caso de sucesso
        return

    except ValueError as e:
        # Erros de validação (senha incorreta, senha fraca) retornam 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Erro inesperado ao atualizar a senha do usuário {current_user['email']}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocorreu um erro interno ao tentar atualizar a senha.",
        )