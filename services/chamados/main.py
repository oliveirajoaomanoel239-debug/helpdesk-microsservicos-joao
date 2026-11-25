"""Serviço independente de chamados, comentários e avisos locais."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.chamados.modelos import Chamado, Comentario  # registra somente tabelas deste serviço
from app.chamados.rotas import router as chamados_router
from app.config import DOCS_ATIVA
from app.database import Base, engine
from app.erros import NaoEncontrado, RegraDeNegocio, SemPermissao
from app.notificacoes.modelos import Notificacao
from app.notificacoes.rotas import router as notificacoes_router
from app.seguranca_http import CabecalhosDeSeguranca


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="HelpDesk — Serviço de Chamados", version="3.0.0", lifespan=lifespan,
              docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None)
app.add_middleware(CabecalhosDeSeguranca)
app.include_router(chamados_router)
app.include_router(notificacoes_router)


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
    return JSONResponse(status_code=409, content={"detail": "Registro em conflito."})


@app.get("/saude", tags=["Saúde"])
def saude():
    return {"servico": "chamados", "status": "ok"}
