"""Mapa de deslocamento, rota até o soro e análise de postos críticos.

O mapa é um grafo: os vértices são localidades (cidades, aldeias, comunidades)
e as arestas são trechos com tempo em horas e meio de transporte (barco,
voadeira, estrada, avião, a pé). As rotas são calculadas aqui mesmo, com o
algoritmo de Dijkstra. Não usamos API de mapas: os serviços comerciais de rota
só conhecem estradas e não sabem que na Amazônia o caminho é pelo rio.

Postos críticos: para cada unidade com soro, o sistema simula a falta de soro
nela e conta quantas comunidades passariam do tempo-limite. Cada simulação é
um Dijkstra independente, então elas rodam em paralelo em vários processos.
"""
from __future__ import annotations

import heapq
import math
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

INF = float("inf")


class Mapa:
    def __init__(self, localidades: dict[str, dict], trechos):
        self.localidades = localidades
        self.adj: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        for a, b, horas, modal in trechos:
            self.adj[a].append((b, float(horas), modal))
            self.adj[b].append((a, float(horas), modal))
        for loc in localidades:
            self.adj.setdefault(loc, [])

    def distancia_km(self, lat: float, lon: float, local: str) -> float:
        l = self.localidades[local]
        return _haversine_km(lat, lon, l["lat"], l["lon"])

    def mais_proxima(self, lat: float, lon: float) -> str:
        """Localidade do mapa mais perto de uma coordenada (distância em linha reta)."""
        return min(self.localidades, key=lambda l: _haversine_km(
            lat, lon, self.localidades[l]["lat"], self.localidades[l]["lon"]))

    def caminhos(self, origem: str) -> tuple[dict[str, float], dict[str, tuple[str, str, float]]]:
        """Dijkstra a partir de ``origem``: tempo até cada localidade e o passo anterior."""
        dist = {origem: 0.0}
        anterior: dict[str, tuple[str, str, float]] = {}
        fila = [(0.0, origem)]
        feitos = set()
        while fila:
            d, v = heapq.heappop(fila)
            if v in feitos:
                continue
            feitos.add(v)
            for w, horas, modal in self.adj[v]:
                if d + horas < dist.get(w, INF):
                    dist[w] = d + horas
                    anterior[w] = (v, modal, horas)
                    heapq.heappush(fila, (d + horas, w))
        return dist, anterior

    def trajeto(self, anterior, destino: str) -> list[dict]:
        passos = []
        v = destino
        while v in anterior:
            u, modal, horas = anterior[v]
            passos.append({"de": u, "para": v, "modal": modal, "horas": horas})
            v = u
        return list(reversed(passos))


def destinos_com_soro(mapa: Mapa, origem: str, candidatos: dict[str, str]) -> list[dict]:
    """Ordena unidades candidatas pelo tempo de chegada a partir de ``origem``.

    ``candidatos`` mapeia id da unidade para a localidade onde ela fica.
    """
    dist, anterior = mapa.caminhos(origem)
    saida = []
    for unidade, local in candidatos.items():
        if dist.get(local, INF) < INF:
            saida.append({"unidade": unidade, "local": local, "horas": round(dist[local], 2),
                          "trajeto": mapa.trajeto(anterior, local)})
    return sorted(saida, key=lambda d: d["horas"])


# --- postos críticos em paralelo --------------------------------------------
# O grafo vai uma vez para cada processo (initializer); cada tarefa recebe só o
# nome do posto a remover.

_ADJ = None
_COBERTAS = None


def _iniciar_trabalhador(adj, cobertas):
    global _ADJ, _COBERTAS
    _ADJ, _COBERTAS = adj, cobertas


def _multiorigem(adj, origens) -> dict[str, float]:
    dist: dict[str, float] = {}
    fila = [(0.0, o) for o in origens]
    heapq.heapify(fila)
    while fila:
        d, v = heapq.heappop(fila)
        if v in dist:
            continue
        dist[v] = d
        for w, horas, _ in adj.get(v, ()):
            if w not in dist:
                heapq.heappush(fila, (d + horas, w))
    return dist


def _sem(args):
    removidos, locais, limite = args
    saida = []
    for r in removidos:
        dist = _multiorigem(_ADJ, [l for l in locais if l != r])
        saida.append((r, sum(1 for c in _COBERTAS if dist.get(c, INF) > limite)))
    return saida


def postos_criticos(adj: dict, comunidades: list[str], locais_com_soro: list[str],
                    limite_horas: float, processos: int = 1) -> tuple[dict[str, int], float]:
    """Para cada local com soro, quantas comunidades hoje cobertas passam do limite sem ele.

    Devolve (resultado, segundos gastos).
    """
    inicio = time.perf_counter()
    locais = sorted(set(locais_com_soro))
    base = _multiorigem(adj, locais)
    cobertas = [c for c in comunidades if base.get(c, INF) <= limite_horas]
    if processos <= 1 or len(locais) < 2:
        _iniciar_trabalhador(adj, cobertas)
        resultado = dict(_sem((locais, locais, limite_horas)))
    else:
        blocos = [locais[i::processos * 4] for i in range(processos * 4)]
        resultado = {}
        with ProcessPoolExecutor(processos, initializer=_iniciar_trabalhador, initargs=(adj, cobertas)) as pool:
            for parcial in pool.map(_sem, [(b, locais, limite_horas) for b in blocos if b]):
                resultado.update(parcial)
    return resultado, time.perf_counter() - inicio


def mapa_sintetico(lado: int, n_postos: int, semente: int = 1):
    """Malha lado x lado de localidades com tempos aleatórios, para medir o ganho do paralelismo."""
    import random
    rng = random.Random(semente)
    adj: dict[str, list] = defaultdict(list)
    nome = lambda i, j: f"c{i}_{j}"
    for i in range(lado):
        for j in range(lado):
            adj.setdefault(nome(i, j), [])
            if i + 1 < lado:
                h = rng.uniform(0.2, 1.5)
                adj[nome(i, j)].append((nome(i + 1, j), h, "rio"))
                adj[nome(i + 1, j)].append((nome(i, j), h, "rio"))
            if j + 1 < lado and rng.random() < 0.6:
                h = rng.uniform(0.5, 3.0)
                adj[nome(i, j)].append((nome(i, j + 1), h, "trilha"))
                adj[nome(i, j + 1)].append((nome(i, j), h, "trilha"))
    todos = list(adj)
    postos = rng.sample(todos, n_postos)
    comunidades = [c for c in todos if c not in set(postos)]
    return dict(adj), comunidades, postos


def medir_speedup(lado: int = 150, n_postos: int = 200, limite: float = 6.0,
                  lista_processos: list[int] | None = None) -> list[dict]:
    adj, comunidades, postos = mapa_sintetico(lado, n_postos)
    if lista_processos is None:
        lista_processos = [p for p in (1, 2, 4, 8, 16) if p <= (os.cpu_count() or 1)]
    linhas, base, ref = [], None, None
    for p in lista_processos:
        r, dt = postos_criticos(adj, comunidades, postos, limite, p)
        if base is None:
            base, ref = dt, r
        if r != ref:
            raise AssertionError("resultado paralelo diferente do sequencial")
        linhas.append({"processos": p, "segundos": round(dt, 2), "speedup": round(base / dt, 2),
                       "eficiencia": round(base / dt / p, 2)})
    return linhas


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
