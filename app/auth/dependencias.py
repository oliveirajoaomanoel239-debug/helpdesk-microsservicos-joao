"""Dependências stateless: todo microsserviço valida localmente o JWT."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import tokens

esquema = HTTPBearer(auto_error=False)

NAO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Faça login para continuar.",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class Principal:
    id: int
    perfil: str
    ativo: bool = True


def usuario_atual(credenciais: HTTPAuthorizationCredentials | None = Depends(esquema)) -> Principal:
    """Valida o token sem consultar o banco de outro serviço."""
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise NAO_AUTENTICADO
    try:
        claims = tokens.ler_dados(credenciais.credentials)
    except tokens.TokenInvalido:
        raise NAO_AUTENTICADO
    return Principal(id=claims["id"], perfil=claims["perfil"])


def exigir_perfil(*perfis: str):
    """Libera a rota só para os perfis informados."""
    def verificar(usuario: Principal = Depends(usuario_atual)) -> Principal:
        if usuario.perfil not in perfis:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Você não tem permissão para esta ação.")
        return usuario
    return verificar
