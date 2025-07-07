import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from jose import jwt, JWTError
from datetime import timedelta

from utils.jwt_utils import SECRET_KEY, ALGORITHM, create_access_token

# Define o tempo mínimo para renovar o token.
# Se o token expirar em menos de 5 minutos, um novo será gerado.
REFRESH_THRESHOLD_MINUTES = 5

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Continua para a rota para que a autenticação normal ocorra primeiro
        response = await call_next(request)

        # Só tenta renovar se a requisição foi bem-sucedida (status 2xx)
        if 200 <= response.status_code < 300:
            token = request.headers.get("Authorization")

            if token and token.startswith("Bearer "):
                token = token.split(" ")[1]
                try:
                    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

                    exp_timestamp = payload.get("exp")
                    current_timestamp = int(time.time())

                    if exp_timestamp:
                        time_left_seconds = exp_timestamp - current_timestamp

                        # Verifica se o tempo restante está abaixo do nosso limite
                        if 0 < time_left_seconds < (REFRESH_THRESHOLD_MINUTES * 60):
                            email = payload.get("sub")
                            if email:
                                # Gera um novo token com a data de expiração renovada
                                new_token = create_access_token(data={"sub": email})
                                # Adiciona o novo token em um cabeçalho customizado na resposta
                                response.headers["X-Access-Token-Refreshed"] = new_token

                except JWTError:
                    # Se o token for inválido, não faz nada. A proteção de rota já terá barrado.
                    pass

        return response