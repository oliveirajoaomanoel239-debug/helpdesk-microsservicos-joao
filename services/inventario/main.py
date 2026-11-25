"""Serviço independente de inventário e ativos."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import DOCS_ATIVA
from app.database import Base, SessionLocal, engine
from app.erros import NaoEncontrado, RegraDeNegocio, SemPermissao
from app.inventario import servico
from app.inventario.esquemas import AtivoCriar
from app.inventario.modelos import Ativo
from app.inventario.rotas import router as inventario_router
from app.seguranca_http import CabecalhosDeSeguranca


def carregar_ativos():
    with SessionLocal() as db:
        if db.query(Ativo).first():
            return
        exemplos = [
            ("PAT-0001", "computador", "Desktop Dell OptiPlex", "Financeiro"),
            ("PAT-0002", "impressora", "Impressora HP LaserJet", "RH"),
            ("PAT-0003", "notebook", "Notebook Lenovo ThinkPad", "TI"),
        ]
        for patrimonio, tipo, descricao, setor in exemplos:
            servico.criar(db, AtivoCriar(patrimonio=patrimonio, tipo=tipo, descricao=descricao, setor=setor))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        carregar_ativos()
    yield


app = FastAPI(title="HelpDesk — Serviço de Inventário", version="3.0.0", lifespan=lifespan,
              docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None)
app.add_middleware(CabecalhosDeSeguranca)
app.include_router(inventario_router)


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
    return {"servico": "inventario", "status": "ok"}
