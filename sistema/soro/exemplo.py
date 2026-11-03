"""Dados de exemplo para demonstração.

Primeiro cria as contas de demonstração (tabela abaixo). Depois tudo entra pela
API HTTP de cada nó, com login, como faria a equipe: lotes de soro,
três semanas de atendimentos (com um aumento de casos no Alto Solimões nos
últimos dias), uma remessa a caminho e um pedido de soro. Os números são
inventados; servem só para as telas terem o que mostrar.
"""
from __future__ import annotations

import json
import random
import time
import urllib.request
import uuid
from datetime import date, timedelta

from .cliente import Cliente, ErroApi

GRAVIDADE = [("leve", 4, 0.55), ("moderado", 8, 0.35), ("grave", 12, 0.10)]  # (gravidade, ampolas, probabilidade)
AGRAVOS = [("botropico", 0.82), ("escorpionico", 0.10), ("laquetico", 0.06), ("elapidico", 0.02)]


def obter(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


# Contas de demonstração, todas com a mesma senha. Servem só para a rede de exemplo.
SENHA_EXEMPLO = "soro-demo-2026"


def contas_exemplo(rede) -> list[dict]:
    """gestor na secretaria, coord.<polo> em cada polo e prof.<unidade> em cada polo e posto."""
    contas = []
    for u in rede.unidades.values():
        if u.nivel == "estado":
            contas.append({"login": "gestor", "nome": "Gestão estadual (demonstração)", "tipo": "gestor", "unidade": u.id})
        if u.nivel == "polo":
            contas.append({"login": f"coord.{u.id}", "nome": f"Coordenação {u.nome} (demonstração)",
                           "tipo": "coordenador", "unidade": u.id})
        if u.nivel in ("polo", "posto"):
            contas.append({"login": f"prof.{u.id}", "nome": f"Profissional {u.nome} (demonstração)",
                           "tipo": "profissional", "unidade": u.id})
    return contas


def operador(u) -> str:
    """Conta usada para lançar os dados de cada unidade (o polo precisa enviar remessas)."""
    return {"estado": "gestor", "polo": f"coord.{u.id}"}.get(u.nivel, f"prof.{u.id}")


def criar_contas(rede, senha: str = SENHA_EXEMPLO) -> dict[str, Cliente]:
    """Cria as contas pela secretaria e devolve um cliente logado em cada nó."""
    estado = next(u for u in rede.unidades.values() if u.nivel == "estado")
    contas = contas_exemplo(rede)
    gestor = Cliente(estado.url)
    if gestor.obter("/api/sessao")["primeiro_acesso"]:
        gestor.postar("/api/usuarios", {**next(c for c in contas if c["tipo"] == "gestor"), "senha": senha})
    gestor.entrar("gestor", senha)
    for c in contas:
        if c["tipo"] != "gestor":
            try:
                gestor.postar("/api/usuarios", {**c, "senha": senha})
            except ErroApi as e:
                if "já existe" not in str(e):
                    raise
    clientes = {estado.id: gestor}
    for u in rede.unidades.values():
        if u.id != estado.id:
            # A conta foi criada na secretaria; o nó só aceita o login quando ela chega pela sincronização.
            clientes[u.id] = Cliente(u.url)
            clientes[u.id].entrar(operador(u), senha, esperar_s=60)
    return clientes


def _post(cliente: Cliente, caminho: str, corpo: dict) -> dict:
    try:
        return cliente.postar(caminho, corpo)
    except ErroApi as e:
        return {"erro": str(e)}


def _sortear(rng, opcoes):
    u, acc = rng.random(), 0.0
    for *valor, p in opcoes:
        acc += p
        if u <= acc:
            return valor
    return opcoes[-1][:-1]


def carregar_exemplo(rede, semente: int = 7) -> None:
    rng = random.Random(semente)
    hoje = date.today()
    estoque_inicial = {
        "estado": {"SAB": 900, "SABL": 200, "SAEsc": 150, "SAEl": 60},
        "polo": {"SAB": 150, "SABL": 50, "SAEsc": 40, "SAEl": 10},
        "posto": {"SAB": 60, "SABL": 15, "SAEsc": 15},
    }
    print("Contas de demonstração (esperando chegarem a todos os nós)...")
    cli = criar_contas(rede)
    print(f"  {len(contas_exemplo(rede))} contas; senha de todas: {SENHA_EXEMPLO}")
    print("Lotes de soro...")
    for u in rede.unidades.values():
        for soro, qtd in estoque_inicial[u.nivel].items():
            if u.id == "umariacu" and soro == "SAEsc":
                continue
            qtd = min(qtd, 45) if u.id == "umariacu" else qtd
            # Dois lotes de cotas diferentes: um vence em 4 a 8 meses, o outro em 10 a 18.
            parte = round(qtd * 0.4)
            for q, dias in ((parte, rng.randint(120, 240)), (qtd - parte, rng.randint(300, 540))):
                if q:
                    _post(cli[u.id], "/api/entradas", {"soro": soro, "lote": f"{soro}-{u.id[:3].upper()}-{rng.randint(100, 999)}",
                                                    "validade": (hoje + timedelta(days=dias)).isoformat(), "qtd": q})
    estado = next(u for u in rede.unidades.values() if u.nivel == "estado")
    _post(cli[estado.id], "/api/entradas", {"soro": "SAB", "lote": "SAB-FVS-VENCE",
                                         "validade": (hoje + timedelta(days=45)).isoformat(), "qtd": 60})

    print("Três semanas de atendimentos...")
    atendem = [u for u in rede.unidades.values() if u.nivel in ("polo", "posto")]
    total = 0
    for dias_atras in range(21, -1, -1):
        dia = hoje - timedelta(days=dias_atras)
        for u in atendem:
            taxa = 0.35
            if u.regiao == "Alto Solimões" and dias_atras <= 1:
                taxa = 2.2  # aumento de casos nos dois últimos dias
            n = rng.randint(2, 3) if taxa > 1 else sum(rng.random() < taxa / 3 for _ in range(3))
            for _ in range(n):
                agravo, = _sortear(rng, AGRAVOS)
                grav, amp = _sortear(rng, GRAVIDADE)
                if agravo == "escorpionico":
                    amp = {"leve": 0, "moderado": 3, "grave": 6}[grav]
                if agravo in ("laquetico", "elapidico"):
                    amp = 10
                _post(cli[u.id], "/api/casos", {"id": uuid.uuid4().hex, "agravo": agravo, "gravidade": grav,
                                             "ampolas": amp, "data": dia.isoformat()})
                total += 1
    print(f"  {total} atendimentos registrados")

    print("Esperando a sincronização...")
    time.sleep(3 * float(rede.param("intervalo_sincronizacao_s", 2.0)))

    polo = rede.unidade("tabatinga") if "tabatinga" in rede.unidades else None
    if polo and "atalaia" in polo.abastece:
        r = _post(cli[polo.id], "/api/remessas", {"destino": "atalaia", "soro": "SAB", "qtd": 20})
        print("  remessa a caminho de Atalaia:", "ok" if r and "erro" not in r else r)
    if "benjamin" in rede.unidades:
        _post(cli["benjamin"], "/api/pedidos", {"soro": "SABL", "qtd": 10})
    for u in rede.unidades.values():
        try:
            cli[u.id].obter("/api/alertas?recalcular=1")
        except (ErroApi, OSError):
            pass
    print("Pronto. Abra os painéis no navegador.")
