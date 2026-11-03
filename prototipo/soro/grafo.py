"""Grafo multimodal de deslocamento e cálculo de acesso ao soro.

Os vértices são localidades (comunidades, postos, polos); as arestas são
trechos com tempo em horas e modal (a pé, voadeira, barco, estrada, avião).
O tempo de acesso de uma comunidade ao soro é a menor distância até qualquer
posto que tenha o soro em estoque -- um Dijkstra com múltiplas origens.

A análise de criticidade "N-1" pergunta, para cada posto: se o estoque dele
zerar, quantas comunidades hoje cobertas passam do tempo-limite? São N Dijkstras
independentes, portanto paralelizáveis sem nenhuma comunicação entre eles.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

INF = float("inf")


class GrafoMultimodal:
    def __init__(self):
        self.adj: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        self.tipo: dict[str, str] = {}
        self.regiao: dict[str, str] = {}

    def adicionar_local(self, nome: str, tipo: str, regiao: str | None = None) -> None:
        self.tipo[nome] = tipo
        self.regiao[nome] = regiao
        self.adj.setdefault(nome, [])

    def adicionar_trecho(self, a: str, b: str, horas: float, modal: str) -> None:
        self.adj[a].append((b, horas, modal))
        self.adj[b].append((a, horas, modal))

    def comunidades(self) -> list[str]:
        return [n for n, t in self.tipo.items() if t == "comunidade"]


def dijkstra_multiorigem(adj, origens) -> tuple[dict[str, float], dict[str, str]]:
    """Distância de cada vértice à origem mais próxima e qual origem é essa."""
    dist: dict[str, float] = {}
    mais_proxima: dict[str, str] = {}
    fila = [(0.0, o, o) for o in origens]
    heapq.heapify(fila)
    while fila:
        d, v, origem = heapq.heappop(fila)
        if v in dist:
            continue
        dist[v] = d
        mais_proxima[v] = origem
        for w, horas, _ in adj.get(v, ()):
            if w not in dist:
                heapq.heappush(fila, (d + horas, w, origem))
    return dist, mais_proxima


def rota(grafo: GrafoMultimodal, origem: str, destinos: set[str]):
    """Menor caminho de ``origem`` até o destino mais próximo do conjunto.

    Devolve (destino, horas, [(local, modal), ...]) ou None se inalcançável.
    """
    dist = {origem: 0.0}
    anterior: dict[str, tuple[str, str]] = {}
    fila = [(0.0, origem)]
    visitados = set()
    while fila:
        d, v = heapq.heappop(fila)
        if v in visitados:
            continue
        visitados.add(v)
        if v in destinos:
            caminho = [(v, "")]
            while v in anterior:
                v, modal = anterior[v]
                caminho.append((v, modal))
            return caminho[0][0], d, list(reversed(caminho))
        for w, horas, modal in grafo.adj[v]:
            if d + horas < dist.get(w, INF):
                dist[w] = d + horas
                anterior[w] = (v, modal)
                heapq.heappush(fila, (d + horas, w))
    return None


def cobertura(grafo: GrafoMultimodal, postos_com_soro: set[str]) -> dict[str, tuple[str | None, float]]:
    """Para cada comunidade: (posto mais próximo com soro, horas)."""
    dist, prox = dijkstra_multiorigem(grafo.adj, postos_com_soro)
    return {c: (prox.get(c), dist.get(c, INF)) for c in grafo.comunidades()}


# --- Criticidade N-1 em paralelo -------------------------------------------
# O grafo é enviado uma única vez para cada processo (initializer), e cada
# tarefa carrega só o nome do posto removido.

_ADJ = None
_COBERTAS = None


def _inicializar_trabalhador(adj, cobertas):
    global _ADJ, _COBERTAS
    _ADJ, _COBERTAS = adj, cobertas


def _descobertas_sem(removido, postos, limite_horas):
    dist, _ = dijkstra_multiorigem(_ADJ, [p for p in postos if p != removido])
    return removido, sum(1 for c in _COBERTAS if dist.get(c, INF) > limite_horas)


def _lote_descobertas(args):
    removidos, postos, limite_horas = args
    return [_descobertas_sem(r, postos, limite_horas) for r in removidos]


def criticidade(grafo: GrafoMultimodal, postos_com_soro: set[str], limite_horas: float,
                trabalhadores: int = 1) -> dict[str, int]:
    """Quantas comunidades perdem a cobertura (passam de ``limite_horas``)
    se cada posto, isoladamente, zerar o estoque."""
    postos = sorted(postos_com_soro)
    adj = dict(grafo.adj)
    cobertas = [c for c, (_, h) in cobertura(grafo, postos_com_soro).items() if h <= limite_horas]
    if trabalhadores <= 1:
        _inicializar_trabalhador(adj, cobertas)
        return dict(_descobertas_sem(p, postos, limite_horas) for p in postos)
    # Divide os postos em blocos para amortizar o custo de cada tarefa.
    blocos = [postos[i::trabalhadores * 4] for i in range(trabalhadores * 4)]
    with ProcessPoolExecutor(trabalhadores, initializer=_inicializar_trabalhador,
                             initargs=(adj, cobertas)) as pool:
        resultado = {}
        for parcial in pool.map(_lote_descobertas, [(b, postos, limite_horas) for b in blocos if b]):
            resultado.update(parcial)
        return resultado
