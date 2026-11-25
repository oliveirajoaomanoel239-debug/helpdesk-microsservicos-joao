"""Serviço independente de identidade e usuários."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.auth.rotas import router as auth_router
from app.config import DOCS_ATIVA
from app.database import Base, SessionLocal, engine
from app.erros import NaoEncontrado, RegraDeNegocio, SemPermissao
from app.seguranca_http import CabecalhosDeSeguranca
from app.usuarios import servico
from app.usuarios.esquemas import UsuarioCriar
from app.usuarios.modelos import Usuario
from app.usuarios.rotas import router as usuarios_router


def carregar_usuarios():
    """Dados didáticos independentes; os IDs são estáveis nos bancos novos."""
    with SessionLocal() as db:
        if db.query(Usuario).first():
            return
        exemplos = [
            ("Admin TI", "admin@empresa.com", "admin"),
            ("Ana Souza", "ana@empresa.com", "solicitante"),
            ("Bruno Lima", "bruno@empresa.com", "solicitante"),
            ("Carla Dias", "carla@empresa.com", "tecnico"),
            ("Diego Rocha", "diego@empresa.com", "tecnico"),
        ]
        senha = os.getenv("SENHA_EXEMPLO", "Helpdesk2026")
        for nome, email, perfil in exemplos:
            servico.criar(db, UsuarioCriar(nome=nome, email=email, perfil=perfil, senha=senha))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        carregar_usuarios()
    yield


app = FastAPI(title="HelpDesk — Serviço de Usuários", version="3.0.0", lifespan=lifespan,
              docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None)
app.add_middleware(CabecalhosDeSeguranca)
app.include_router(auth_router)
app.include_router(usuarios_router)


@app.exception_handler(NaoEncontrado)
def nao_encontrado(request: Request, exc: NaoEncontrado):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(RegraDeNegocio)
def regra(request: Request, exc: RegraDeNegocio):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(SemPermissao)
def permissao(request: Request, exc: SemPermissao):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
def conflito(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Registro já existente."})


@app.get("/saude", tags=["Saúde"])
def saude():
    return {"servico": "usuarios", "status": "ok"}
