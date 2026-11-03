"""Servidor HTTP de um nó com FastAPI: API em JSON, páginas web e pontos de sincronização.

As rotas são funções comuns (``def``, não ``async``): o FastAPI roda cada
requisição numa thread do seu pool, então vários profissionais podem usar o
mesmo nó ao mesmo tempo. As operações que leem e depois gravam o estoque passam
pela trava do nó (ver ``no.py``), para que duas saídas simultâneas não usem o
mesmo frasco. A documentação interativa da API fica em ``/docs`` de cada nó.
"""
from __future__ import annotations

import mimetypes
import threading
import time
import traceback
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI, Path as Caminho, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .no import ErroNegocio, No
from .sincronizacao import Sincronizador

PASTA_WEB = Path(__file__).parent / "web"
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("text/javascript", ".js")


# --- corpos das requisições ---------------------------------------------------
# Os campos seguem o que as telas enviam. As regras de negócio (quantidade
# positiva, lote existente, espaço na geladeira) continuam em no.py.

class TrocaSync(BaseModel):
    vetor: dict[str, int] = Field(default_factory=dict, description="quantos eventos o nó tem de cada origem")
    contatos: dict[str, float] = Field(default_factory=dict, description="último contato conhecido com cada unidade")


class EventosSync(BaseModel):
    eventos: list[dict] = Field(default_factory=list)
    contatos: dict[str, float] = Field(default_factory=dict)


class Entrada(BaseModel):
    soro: str = Field(examples=["SAB"])
    lote: str = Field(examples=["SAB-2026-117"])
    validade: str = Field(description="AAAA-MM-DD", examples=["2027-12-31"])
    qtd: int


class Perda(BaseModel):
    lote: str
    qtd: int
    motivo: str = "perda"


class Caso(BaseModel):
    id: str | None = Field(None, description="gerado pelo navegador; reenviar o mesmo id não duplica o caso")
    agravo: str = Field(examples=["botropico"])
    gravidade: str = Field("moderado", examples=["leve", "moderado", "grave"])
    ampolas: int = 0
    local: str | None = None
    data: str | None = Field(None, description="AAAA-MM-DD; sem data, usa hoje")


class Remessa(BaseModel):
    destino: str
    soro: str
    qtd: int
    pedido: str | None = Field(None, description="id do pedido que esta remessa atende")


class Recebimento(BaseModel):
    qtd: int | None = Field(None, description="quantidade que chegou; sem valor, a remessa chegou inteira")


class Pedido(BaseModel):
    soro: str
    qtd: int


def criar_app(no: No, sync: Sincronizador) -> FastAPI:
    app = FastAPI(title=f"Soro · {no.u.nome}", version="0.3",
                  description=f"API do nó {no.u.id} ({no.u.nivel}) da rede de soros de {no.rede.estado}.")

    # --- erros no formato que as telas esperam: {"erro": "..."} -----------------
    @app.exception_handler(ErroNegocio)
    def erro_negocio(_: Request, e: ErroNegocio):
        return JSONResponse({"erro": str(e)}, status_code=409)

    @app.exception_handler(KeyError)
    def nao_encontrado(_: Request, e: KeyError):
        return JSONResponse({"erro": f"não encontrado: {e}"}, status_code=404)

    @app.exception_handler(RequestValidationError)
    def dados_invalidos(_: Request, e: RequestValidationError):
        campos = "; ".join(f"{'.'.join(str(x) for x in err['loc'][1:]) or 'corpo'}: {err['msg']}" for err in e.errors())
        return JSONResponse({"erro": f"Dados inválidos ({campos})"}, status_code=422)

    @app.exception_handler(Exception)
    def erro_interno(_: Request, e: Exception):
        traceback.print_exc()
        return JSONResponse({"erro": f"erro interno: {e}"}, status_code=500)

    # O estoque muda a todo momento: nada de cache no navegador (o service worker
    # da tela do cidadão guarda o que precisa por conta própria).
    @app.middleware("http")
    async def sem_cache(request: Request, chamar):
        resposta = await chamar(request)
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

    # --- sincronização -------------------------------------------------------
    r = APIRouter(tags=["sincronização"])

    @r.post("/sync", summary="Primeira metade da troca: recebe o vetor do vizinho e devolve o que falta a ele")
    def sync_pedido(c: TrocaSync):
        d = no.diario
        d.juntar_contatos(c.contatos)
        d.marcar_contato(no.u.id)
        return {"eventos": d.desde(c.vetor), "vetor": d.vetor(), "contatos": d.contatos()}

    @r.post("/sync/eventos", summary="Segunda metade da troca: recebe os eventos que faltavam aqui")
    def sync_eventos(c: EventosSync):
        novos = no.diario.incorporar(c.eventos)
        no.diario.juntar_contatos(c.contatos)
        return {"novos": len(novos)}

    @r.get("/api/sincronizacao", summary="Vetor de versões, total, resumo e estado dos vizinhos")
    def api_sincronizacao():
        d = no.diario
        return {"vetor": d.vetor(), "eventos": d.total(), "resumo": d.resumo(), **sync.estado()}

    @r.get("/api/contagem", summary="Quantos eventos, casos, remessas, pedidos e alertas o nó conhece")
    def api_contagem():
        v = no._visao()
        return {"eventos": no.diario.total(), "casos": len(v["casos"]),
                "remessas": len(v["remessas"]), "pedidos": len(v["pedidos"]), "alertas": len(v["alertas"])}

    @r.post("/api/sincronizar", summary="Força uma troca com cada vizinho agora")
    def api_sincronizar():
        return {"resultado": {v: sync.trocar(v) for v in sync.vizinhos}}

    app.include_router(r)

    # --- informação e estoque -------------------------------------------------
    r = APIRouter(prefix="/api", tags=["estoque"])

    @r.get("/info", summary="Dados do nó e da rede")
    def api_info():
        return no.info()

    @r.get("/estoque", summary="Lotes, total, capacidade, espaço livre e remessas a caminho de uma unidade")
    def api_estoque(unidade: str | None = None):
        uid = unidade or no.u.id
        return {"unidade": uid, "lotes": no.lotes(uid), "total": no.total_estoque(uid),
                "capacidade": no.rede.unidade(uid).capacidade, "livre": no.espaco_livre(uid),
                "a_caminho": no.em_transito(uid), "atualizado_ha_s": no.idade(uid),
                "disponivel": {s: no.disponivel(uid, s) for s in no.rede.soros}}

    @r.post("/entradas", status_code=201, summary="Entrada de lote vindo de fora da rede")
    def api_entrada(c: Entrada):
        return no.registrar_entrada(c.soro, c.lote, c.validade, c.qtd)

    @r.post("/perdas", status_code=201, summary="Perda ou descarte de ampolas de um lote")
    def api_perda(c: Perda):
        return no.registrar_perda(c.lote, c.qtd, c.motivo)

    app.include_router(r)

    # --- atendimento ------------------------------------------------------------
    r = APIRouter(prefix="/api", tags=["atendimento"])

    @r.post("/casos", status_code=201, summary="Registra um atendimento e dá baixa no soro")
    def api_novo_caso(c: Caso, resposta: Response):
        caso = no.atender(c.agravo, c.gravidade, c.ampolas, c.local, c.id, c.data)
        if caso.get("repetido"):
            resposta.status_code = 200
        return caso

    @r.get("/casos", summary="Últimos atendimentos (até 200)")
    def api_casos(regiao: str | None = None, unidade: str | None = None):
        return no.casos(regiao, unidade)[:200]

    app.include_router(r)

    # --- remessas e pedidos ---------------------------------------------------
    r = APIRouter(prefix="/api", tags=["remessas e pedidos"])

    @r.get("/remessas", summary="Remessas chegando, enviadas e pedidos em aberto")
    def api_remessas():
        return {"chegando": no.em_transito(no.u.id),
                "enviadas": [x for x in no.em_transito() if x["origem"] == no.u.id],
                "pedidos_recebidos": no.pedidos_abertos(no.u.id),
                "meus_pedidos": [p for p in no.pedidos_abertos() if p["unidade"] == no.u.id]}

    @r.post("/remessas", status_code=201, summary="Envia uma remessa para outra unidade")
    def api_enviar(c: Remessa):
        return no.enviar_remessa(c.destino, c.soro, c.qtd, c.pedido)

    @r.post("/remessas/{rid}/receber", status_code=201, summary="Confirma o recebimento, informando divergência")
    def api_receber(rid: str = Caminho(pattern="^[0-9a-f]+$"), c: Recebimento | None = None):
        return no.receber_remessa(rid, c.qtd if c else None)

    @r.post("/pedidos", status_code=201, summary="Pede soro ao fornecedor desta unidade")
    def api_pedir(c: Pedido):
        return no.pedir(c.soro, c.qtd)

    @r.get("/sugestoes", summary="Quanto mandar para cada unidade abastecida por esta")
    def api_sugestoes():
        return no.sugestoes()

    app.include_router(r)

    # --- vigilância e painéis ---------------------------------------------------
    r = APIRouter(prefix="/api", tags=["vigilância e painéis"])

    @r.get("/alertas", summary="Alertas de surto ativos")
    def api_alertas(regiao: str | None = None, recalcular: bool = False):
        if recalcular:
            no.vigiar()
        return no.alertas_ativos(regiao)

    @r.get("/vigilancia", summary="Casos por dia e limite do método C2 por região")
    def api_vigilancia():
        regioes = no.regioes_vigiadas() or ([no.u.regiao] if no.u.regiao else [])
        return [{"regiao": g, "serie": no.serie_regiao(g), "alertas": no.alertas_ativos(g)} for g in regioes]

    @r.get("/painel", summary="Painel do polo ou do estado")
    def api_painel():
        return no.painel()

    @r.get("/graficos", summary="Séries dos gráficos: uso diário, atendimentos e vencimento")
    def api_graficos(dias: int = 30, unidade: str | None = None):
        return no.graficos(max(7, min(90, dias)), unidade)

    @r.get("/criticos", summary="Postos críticos, calculados em paralelo")
    def api_criticos(soro: str = "SAB", processos: int = 1):
        return no.criticos(soro, max(1, min(32, processos)))

    app.include_router(r)

    # --- cidadão: onde tem soro -------------------------------------------------
    r = APIRouter(prefix="/api", tags=["cidadão"])

    @r.get("/localidades", summary="Mapa: localidades, trechos e unidades")
    def api_localidades():
        rede = no.rede
        return {"localidades": list(rede.localidades.values()), "trechos": rede.trechos,
                "unidades": {k: {"nome": u.nome, "local": u.local, "nivel": u.nivel,
                                 "estabelecimento": (u.estabelecimento or {}).get("nome")}
                             for k, u in rede.unidades.items()}}

    @r.get("/onde-tem-soro", summary="Lugares com soro, do mais rápido ao mais lento, com o caminho")
    def api_onde(local: str | None = Query(None, description="id da localidade de saída"),
                 lat: float | None = None, lon: float | None = None,
                 agravo: str | None = Query(None, examples=["botropico"])):
        distancia = None
        if lat is not None and lon is not None:
            origem = no.mapa.mais_proxima(lat, lon)
            distancia = round(no.mapa.distancia_km(lat, lon, origem), 1)
        else:
            origem = local or no.u.local
        soros = no.rede.agravos[agravo]["soros"] if agravo in no.rede.agravos else list(no.rede.soros)
        minimo = int(no.rede.param("ampolas_minimas_busca", 4))
        return {"origem": origem, "origem_nome": no.rede.localidades[origem]["nome"], "distancia_km": distancia,
                "soros": soros, "minimo": minimo, "destinos": no.onde_tem_soro(origem, soros, minimo)[:5]}

    app.include_router(r)

    # Páginas: por último, para não esconder as rotas da API.
    app.mount("/", StaticFiles(directory=PASTA_WEB, html=True), name="paginas")
    return app


class ServidorNo:
    """Junta nó, sincronizador, vigilância periódica e servidor HTTP (uvicorn)."""

    def __init__(self, no: No, intervalo_sync: float | None = None, host: str | None = None):
        self.no = no
        intervalo_sync = intervalo_sync or float(no.rede.param("intervalo_sincronizacao_s", 2.0))
        self.sync = Sincronizador(no, intervalo_sync)
        self.app = criar_app(no, self.sync)
        self.http = uvicorn.Server(uvicorn.Config(self.app, host=host or no.u.host, port=no.u.porta,
                                                  log_level="warning", access_log=False))
        self._parar = threading.Event()
        self._vigia = threading.Thread(target=self._vigiar, daemon=True, name=f"vigia-{no.u.id}")
        self._thread_http: threading.Thread | None = None

    def _vigiar(self):
        intervalo = float(self.no.rede.param("intervalo_vigilancia_s", 10.0))
        while not self._parar.wait(intervalo):
            try:
                self.no.vigiar()
            except Exception:
                traceback.print_exc()

    def iniciar(self, bloquear: bool = True):
        self.no.diario.marcar_contato(self.no.u.id)
        self.sync.iniciar()
        if self.no.regioes_vigiadas():
            self._vigia.start()
        if bloquear:
            self.http.run()
            return
        self._thread_http = threading.Thread(target=self.http.run, daemon=True, name=f"http-{self.no.u.id}")
        self._thread_http.start()
        limite = time.monotonic() + 10
        while not self.http.started and time.monotonic() < limite:
            time.sleep(0.05)

    def parar(self):
        self._parar.set()
        self.sync.parar()
        self.http.should_exit = True
        if self._thread_http:
            self._thread_http.join(timeout=10)
        self.no.diario.fechar()
