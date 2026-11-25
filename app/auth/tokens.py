"""Criação e validação dos tokens JWT compartilhados pelos serviços."""
from datetime import datetime, timedelta, timezone

import jwt

from app.config import JWT_ALGORITMO, JWT_EMISSOR, JWT_SEGREDO, TOKEN_MINUTOS


class TokenInvalido(Exception):
    pass


def criar(usuario_id: int, perfil: str) -> tuple[str, datetime]:
    agora = datetime.now(timezone.utc)
    expira = agora + timedelta(minutes=TOKEN_MINUTOS)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iat": agora, "exp": expira, "iss": JWT_EMISSOR}
    return jwt.encode(dados, JWT_SEGREDO, algorithm=JWT_ALGORITMO), expira


def ler_dados(token: str) -> dict:
    """Valida assinatura, emissor e expiração; retorna claims mínimos."""
    try:
        dados = jwt.decode(
            token, JWT_SEGREDO, algorithms=[JWT_ALGORITMO], issuer=JWT_EMISSOR,
            options={"require": ["exp", "iat", "sub", "iss", "perfil"]},
        )
        usuario_id = int(dados["sub"])
        perfil = dados["perfil"]
        if usuario_id <= 0 or perfil not in {"solicitante", "tecnico", "admin"}:
            raise ValueError("claims inválidos")
        return {"id": usuario_id, "perfil": perfil}
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as erro:
        raise TokenInvalido() from erro


def ler(token: str) -> int:
    """Compatibilidade: devolve somente o id do usuário."""
    return ler_dados(token)["id"]
