"""API Gateway: única entrada pública do HelpDesk."""
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

WEB = Path(__file__).resolve().parents[1] / "app" / "web"
SERVICOS = {
    "usuarios": os.getenv("URL_USUARIOS", "http://usuarios:8000"),
    "inventario": os.getenv("URL_INVENTARIO", "http://inventario:8000"),
    "chamados": os.getenv("URL_CHAMADOS", "http://chamados:8000"),
}
app = FastAPI(title="HelpDesk — API Gateway", version="3.0.0", docs_url=None, redoc_url=None)


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(WEB / "index.html")


@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse(WEB / "app.js", media_type="text/javascript")


@app.get("/estilo.css", include_in_schema=False)
def css():
    return FileResponse(WEB / "estilo.css", media_type="text/css")


@app.get("/saude", tags=["Saúde"])
async def saude():
    resultados = {}
    async with httpx.AsyncClient(timeout=1.5) as client:
        for nome, base in SERVICOS.items():
            try:
                r = await client.get(f"{base}/saude")
                resultados[nome] = "ok" if r.is_success else f"indisponível ({r.status_code})"
            except httpx.HTTPError:
                resultados[nome] = "indisponível"
    return {"status": "ok" if all(v == "ok" for v in resultados.values()) else "degradado",
            "servicos": resultados}


def destino(path: str):
    if path == "auth" or path.startswith("auth/") or path == "usuarios" or path.startswith("usuarios/"):
        return SERVICOS["usuarios"]
    if path == "ativos" or path.startswith("ativos/"):
        return SERVICOS["inventario"]
    if path == "chamados" or path.startswith("chamados/") or path == "notificacoes" or path.startswith("notificacoes/"):
        return SERVICOS["chamados"]
    return None


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
               include_in_schema=False)
async def encaminhar(path: str, request: Request):
    base = destino(path)
    if base is None:
        return JSONResponse(status_code=404, content={"detail": "Rota não encontrada no gateway."})
    query = request.url.query
    url = f"{base}/{path}" + (f"?{query}" if query else "")
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in {"host", "content-length", "connection"}}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0)) as client:
            upstream = await client.request(request.method, url, content=await request.body(), headers=headers)
    except (httpx.TimeoutException, httpx.ConnectError):
        return JSONResponse(status_code=503, content={
            "detail": "Serviço temporariamente indisponível. Tente novamente em instantes."
        })
    ignorar = {"content-encoding", "transfer-encoding", "connection"}
    resposta_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in ignorar}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=resposta_headers)
