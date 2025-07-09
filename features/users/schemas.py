from pydantic import BaseModel


class UserCreate(BaseModel):
    nome: str
    email: str
    senha: str
    confirmar_senha: str
