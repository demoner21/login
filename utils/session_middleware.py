import os
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from jose import jwt, JWTError
from datetime import timedelta
from dotenv import load_dotenv

from utils.jwt_utils import SECRET_KEY, ALGORITHM, create_access_token

load_dotenv()

REFRESH_THRESHOLD_MINUTES = int(os.getenv("REFRESH_THRESHOLD_MINUTES", 5))

class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        excluded_paths = ["/api/v1/auth/token", "/api/v1/auth/logout"]
        if request.url.path in excluded_paths:
            return response

        if response.status_code and 200 <= response.status_code < 300:
            token = request.headers.get("Authorization")

            if token:
                try:
                    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

                    exp_timestamp = payload.get("exp")
                    current_timestamp = int(time.time())

                    if exp_timestamp:
                        time_left_seconds = exp_timestamp - current_timestamp

                        if 0 < time_left_seconds < (REFRESH_THRESHOLD_MINUTES * 60):
                            email = payload.get("sub")
                            if email:
                                new_token = create_access_token(data={"sub": email})
                                
                                response.set_cookie(
                                    key="access_token",
                                    value=new_token,
                                    httponly=True,
                                    samesite='lax',
                                    secure=True,          # Para produção (HTTPS). Mude para False para testes em HTTP local.
                                    path="/"
                                )

                except JWTError:
                    # Se o token for inválido, não faz nada.
                    # A proteção de rota na dependência (get_current_user) já terá barrado a requisição.
                    pass

        return response