from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    nome: str
    email: str
    senha: str
    confirmar_senha: str

class PasswordUpdate(BaseModel):
    """Schema para a requisição de atualização de senha."""
    senha_atual: str
    nova_senha: str

class UserUpdate(BaseModel):
    """Schema para a requisição de atualização de dados do usuário."""
    nome: Optional[str] = None
    email: Optional[EmailStr] = None

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    """Schema para a resposta de dados do usuário (sem a senha)."""
    id: int
    nome: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True