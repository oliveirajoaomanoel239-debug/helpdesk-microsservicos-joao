"""Regras de chamados. Dependências externas são consultadas por HTTP."""
import os
from collections import Counter
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.chamados import repositorio
from app.chamados.esquemas import ChamadoCriar, ComentarioCriar
from app.chamados.modelos import Chamado, Comentario
from app.erros import NaoEncontrado, RegraDeNegocio, SemPermissao
from app.notificacoes import servico as notificacoes

HORAS_SLA = {"critica": 4, "alta": 8, "media": 24, "baixa": 72}
TRANSICOES = {
    "aberto": {"em_atendimento"},
    "em_atendimento": {"resolvido"},
    "resolvido": {"fechado", "em_atendimento"},
    "fechado": set(),
}
EQUIPE = ("tecnico", "admin")


def eh_equipe(usuario) -> bool:
    return usuario.perfil in EQUIPE


def calcular_prazo(prioridade: str, inicio: datetime) -> datetime:
    return inicio + timedelta(hours=HORAS_SLA[prioridade])


def _consultar_servico(base: str, caminho: str, authorization: str) -> dict:
    """HTTP inter-service com autenticação propagada e timeout curto."""
    try:
        resposta = httpx.get(
            f"{base.rstrip('/')}/{caminho.lstrip('/')}",
            headers={"Authorization": authorization},
            timeout=httpx.Timeout(2.5, connect=1.5),
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Serviço dependente indisponível. Tente novamente em instantes.",
        )
    if resposta.status_code == 404:
        raise NaoEncontrado("Registro dependente não encontrado.")
    if resposta.status_code >= 500:
        raise HTTPException(status_code=503, detail="Serviço dependente apresentou uma falha.")
    if not resposta.is_success:
        detalhe = resposta.json().get("detail", "Não foi possível validar o registro relacionado.")
        raise RegraDeNegocio(detalhe)
    return resposta.json()


def _validar_ativo(db: Session, ativo_id: int, authorization: str | None):
    if authorization and os.getenv("MODO_MONOLITO") != "1":
        base = os.getenv("URL_INVENTARIO", "http://inventario:8000")
        return _consultar_servico(base, f"ativos/{ativo_id}", authorization)
    # Compatibilidade com os testes e execução do monólito original.
    from app.inventario import servico as inventario
    return inventario.obter(db, ativo_id)


def _validar_tecnico(db: Session, tecnico_id: int, authorization: str | None):
    if authorization and os.getenv("MODO_MONOLITO") != "1":
        base = os.getenv("URL_USUARIOS", "http://usuarios:8000")
        tecnico = _consultar_servico(base, f"usuarios/{tecnico_id}", authorization)
        if tecnico.get("perfil") != "tecnico":
            raise RegraDeNegocio(f"Usuário {tecnico_id} não é técnico.")
        return tecnico
    from app.usuarios import servico as usuarios
    return usuarios.obter_tecnico(db, tecnico_id)


def abrir(db: Session, dados: ChamadoCriar, usuario, authorization: str | None = None) -> Chamado:
    if dados.ativo_id is not None:
        _validar_ativo(db, dados.ativo_id, authorization)  # chamada HTTP em microsserviços
    agora = datetime.now()
    chamado = repositorio.salvar(db, Chamado(
        **dados.model_dump(), solicitante_id=usuario.id, status="aberto", criado_em=agora,
        prazo_sla=calcular_prazo(dados.prioridade, agora),
    ))
    notificacoes.notificar(
        db, "ChamadoAberto", usuario.id,
        f"Seu chamado #{chamado.id} foi aberto. Prazo: {chamado.prazo_sla:%d/%m %H:%M}.",
    )
    return chamado


def obter(db: Session, chamado_id: int, usuario) -> Chamado:
    chamado = repositorio.buscar_por_id(db, chamado_id)
    if chamado is None or not (eh_equipe(usuario) or chamado.solicitante_id == usuario.id):
        raise NaoEncontrado(f"Chamado {chamado_id} não encontrado.")
    return chamado


def listar(db: Session, usuario, status: str | None = None, tecnico_id: int | None = None) -> list[Chamado]:
    solicitante_id = None if eh_equipe(usuario) else usuario.id
    return repositorio.listar(db, status, tecnico_id, solicitante_id)


def atribuir(db: Session, chamado_id: int, tecnico_id: int, usuario, authorization: str | None = None) -> Chamado:
    if not eh_equipe(usuario):
        raise SemPermissao("Só técnicos e administradores atribuem chamados.")
    chamado = obter(db, chamado_id, usuario)
    if chamado.status in ("resolvido", "fechado"):
        raise RegraDeNegocio("Não é possível atribuir um chamado resolvido ou fechado.")
    tecnico = _validar_tecnico(db, tecnico_id, authorization)
    chamado.tecnico_id = tecnico_id if authorization else tecnico.id
    if chamado.status == "aberto":
        chamado.status = "em_atendimento"
    repositorio.salvar(db, chamado)
    notificacoes.notificar(db, "ChamadoAtribuido", tecnico_id, f"O chamado #{chamado.id} foi atribuído a você.")
    return chamado


def mudar_status(db: Session, chamado_id: int, novo_status: str, usuario) -> Chamado:
    chamado = obter(db, chamado_id, usuario)
    pode_solicitante = chamado.status == "resolvido" and novo_status in ("fechado", "em_atendimento")
    if not (eh_equipe(usuario) or pode_solicitante):
        raise SemPermissao("Você não pode mudar o status deste chamado.")
    if novo_status not in TRANSICOES[chamado.status]:
        raise RegraDeNegocio(f"Não é possível ir de '{chamado.status}' para '{novo_status}'.")
    if novo_status == "em_atendimento" and chamado.tecnico_id is None:
        raise RegraDeNegocio("Atribua um técnico antes de iniciar o atendimento.")
    chamado.status = novo_status
    repositorio.salvar(db, chamado)
    if novo_status == "resolvido":
        notificacoes.notificar(
            db, "ChamadoResolvido", chamado.solicitante_id,
            f"Seu chamado #{chamado.id} foi resolvido. Confirme se está tudo certo.",
        )
    return chamado


def comentar(db: Session, chamado_id: int, dados: ComentarioCriar, usuario) -> Comentario:
    chamado = obter(db, chamado_id, usuario)
    if chamado.status == "fechado":
        raise RegraDeNegocio("Chamados fechados não recebem comentários.")
    return repositorio.salvar_comentario(db, Comentario(
        chamado_id=chamado.id, autor_id=usuario.id, texto=dados.texto, criado_em=datetime.now()
    ))


def painel(db: Session, usuario) -> dict:
    chamados = listar(db, usuario)
    agora = datetime.now()
    atrasados = sum(1 for c in chamados if c.status in ("aberto", "em_atendimento") and c.prazo_sla < agora)
    return {"total": len(chamados), "por_status": dict(Counter(c.status for c in chamados)), "atrasados": atrasados}
