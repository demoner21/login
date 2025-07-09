import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from jose import jwt, JWTError
from datetime import timedelta

from config import settings
from features.auth.service import create_access_token


class TokenRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        excluded_paths = ["/api/v1/auth/token", "/api/v1/auth/logout"]
        if any(request.url.path.startswith(p) for p in excluded_paths):
            return response

        token = request.cookies.get("access_token")

        if token and response.status_code < 400:
            token = request.headers.get("Authorization")

            if token:
                try:
                    payload = jwt.decode(
                        token, SECRET_KEY, algorithms=[ALGORITHM])

                    exp_timestamp = payload.get("exp")
                    current_timestamp = int(time.time())

                    if exp_timestamp:
                        time_left_seconds = exp_timestamp - current_timestamp

                        if 0 < time_left_seconds < (REFRESH_THRESHOLD_MINUTES * 60):
                            email = payload.get("sub")

                            if email:
                                new_token = create_access_token(
                                    data={"sub": email})

                                response.set_cookie(
                                    key="access_token",
                                    value=new_token,
                                    httponly=True,
                                    # Para produção (HTTPS). Mude para False para testes em HTTP local.
                                    samesite='lax',
                                    secure=True,
                                    path="/"
                                )

                except JWTError:
                    # Se o token for inválido, não faz nada.
                    # A proteção de rota na dependência (get_current_user) já terá barrado a requisição.
                    pass

        return response
