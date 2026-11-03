"""Mede o ganho da análise de criticidade N-1 em paralelo num grafo sintético.

Para cada posto, remove-o e roda um Dijkstra multiorigem sobre o grafo
inteiro: são P tarefas independentes, distribuídas entre processos.

    python bench_paralelo.py
    python bench_paralelo.py --lado 300 --postos 400 --trabalhadores 1,2,4,8
"""
import argparse
import os
import random
import time

from soro.grafo import GrafoMultimodal, criticidade


def grafo_sintetico(lado: int, n_postos: int, semente: int = 1):
    """Malha lado x lado de comunidades com tempos aleatórios (rio, estrada, trilha)."""
    rng = random.Random(semente)
    g = GrafoMultimodal()
    nome = lambda i, j: f"c{i}_{j}"
    for i in range(lado):
        for j in range(lado):
            g.adicionar_local(nome(i, j), "comunidade")
    for i in range(lado):
        for j in range(lado):
            if i + 1 < lado:
                g.adicionar_trecho(nome(i, j), nome(i + 1, j), rng.uniform(0.2, 1.5), "rio")
            if j + 1 < lado and rng.random() < 0.6:
                g.adicionar_trecho(nome(i, j), nome(i, j + 1), rng.uniform(0.5, 3.0), "trilha")
    postos = set()
    while len(postos) < n_postos:
        c = nome(rng.randrange(lado), rng.randrange(lado))
        g.tipo[c] = "posto"
        postos.add(c)
    return g, postos


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lado", type=int, default=150, help="malha lado x lado (vértices = lado²)")
    p.add_argument("--postos", type=int, default=200)
    p.add_argument("--limite", type=float, default=6.0)
    padrao = ",".join(str(t) for t in (1, 2, 4, 8, 16) if t <= (os.cpu_count() or 1))
    p.add_argument("--trabalhadores", default=padrao)
    a = p.parse_args()

    g, postos = grafo_sintetico(a.lado, a.postos)
    arestas = sum(len(v) for v in g.adj.values()) // 2
    print(f"Grafo: {len(g.adj)} vértices, {arestas} trechos, {len(postos)} postos; "
          f"{os.cpu_count()} núcleos lógicos disponíveis\n")
    print(f"{'processos':>9} {'tempo (s)':>10} {'speedup':>8} {'eficiência':>11}")
    base, referencia = None, None
    for t in (int(x) for x in a.trabalhadores.split(",")):
        inicio = time.perf_counter()
        r = criticidade(g, postos, a.limite, trabalhadores=t)
        dt = time.perf_counter() - inicio
        if base is None:
            base, referencia = dt, r
        assert r == referencia, "resultado paralelo difere do serial"
        print(f"{t:>9} {dt:>10.2f} {base / dt:>8.2f} {base / dt / t:>10.0%}")
    pior = max(referencia.items(), key=lambda kv: kv[1])
    print(f"\nPosto mais crítico: {pior[0]} (sem ele, {pior[1]} comunidades hoje cobertas "
          f"passariam de {a.limite:.0f} h)")


if __name__ == "__main__":
    main()
