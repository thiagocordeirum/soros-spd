"""Dados de exemplo para demonstração.

Tudo entra pela API HTTP de cada nó, como faria um usuário: lotes de soro,
três semanas de atendimentos (com um aumento de casos no Alto Solimões nos
últimos dias), uma remessa a caminho e um pedido de soro. Os números são
inventados; servem só para as telas terem o que mostrar.
"""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta

from .sincronizacao import postar

GRAVIDADE = [("leve", 4, 0.55), ("moderado", 8, 0.35), ("grave", 12, 0.10)]  # (gravidade, ampolas, probabilidade)
AGRAVOS = [("botropico", 0.82), ("escorpionico", 0.10), ("laquetico", 0.06), ("elapidico", 0.02)]


def obter(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


def _post(url: str, corpo: dict) -> dict | None:
    try:
        return postar(url, corpo)
    except urllib.error.HTTPError as e:
        return {"erro": json.loads(e.read() or b"{}").get("erro", str(e))}


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
                    _post(f"{u.url}/api/entradas", {"soro": soro, "lote": f"{soro}-{u.id[:3].upper()}-{rng.randint(100, 999)}",
                                                    "validade": (hoje + timedelta(days=dias)).isoformat(), "qtd": q})
    estado = next(u for u in rede.unidades.values() if u.nivel == "estado")
    _post(f"{estado.url}/api/entradas", {"soro": "SAB", "lote": "SAB-FVS-VENCE",
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
                _post(f"{u.url}/api/casos", {"id": uuid.uuid4().hex, "agravo": agravo, "gravidade": grav,
                                             "ampolas": amp, "data": dia.isoformat()})
                total += 1
    print(f"  {total} atendimentos registrados")

    print("Esperando a sincronização...")
    time.sleep(3 * float(rede.param("intervalo_sincronizacao_s", 2.0)))

    polo = rede.unidade("tabatinga") if "tabatinga" in rede.unidades else None
    if polo and "atalaia" in polo.abastece:
        r = _post(f"{polo.url}/api/remessas", {"destino": "atalaia", "soro": "SAB", "qtd": 20})
        print("  remessa a caminho de Atalaia:", "ok" if r and "erro" not in r else r)
    if "benjamin" in rede.unidades:
        _post(f"{rede.unidade('benjamin').url}/api/pedidos", {"soro": "SABL", "qtd": 10})
    for u in rede.unidades.values():
        try:
            obter(f"{u.url}/api/alertas?recalcular=1")
        except OSError:
            pass
    print("Pronto. Abra os painéis no navegador.")
