"""Avaliação: as quatro perguntas do slide, medidas com processos reais.

Sobe a rede inteira numa pasta temporária (um processo por nó, comunicando por
HTTP), derruba nós de propósito e mede:

1. Falha de um nó: com o polo fora do ar, os postos continuam registrando?
2. Dados iguais: com vários nós gravando ao mesmo tempo, quanto demora para
   todos terem o mesmo conjunto de eventos (mesmo resumo)?
3. Nada se perde: todo caso enviado aparece em todos os nós uma vez só, mesmo
   quando o cliente reenvia o mesmo caso?
4. Velocidade: quanto o cálculo de postos críticos ganha com mais processos?
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.error
import uuid
from argparse import Namespace
from pathlib import Path

from .__main__ import carregar_rede, esperar_no, iniciar_processo
from .cliente import Cliente, ErroApi
from .exemplo import SENHA_EXEMPLO, criar_contas, obter, operador
from .rotas import medir_speedup


def _caso(cliente: Cliente, cid: str | None = None) -> int:
    corpo = {"id": cid or uuid.uuid4().hex, "agravo": "escorpionico", "gravidade": "leve", "ampolas": 0}
    try:
        cliente.postar("/api/casos", corpo)
        return 1
    except (ErroApi, urllib.error.URLError, OSError):
        return 0


def _resumos(rede, vivos) -> dict[str, str]:
    saida = {}
    for uid in vivos:
        try:
            saida[uid] = obter(rede.unidade(uid).url + "/api/sincronizacao")["resumo"]
        except OSError:
            saida[uid] = None
    return saida


def _esperar_convergencia(rede, vivos, tempo_limite=60.0) -> float | None:
    inicio = time.time()
    while time.time() - inicio < tempo_limite:
        r = _resumos(rede, vivos)
        if None not in r.values() and len(set(r.values())) == 1:
            return time.time() - inicio
        time.sleep(0.05)
    return None


def avaliar(args) -> None:
    pasta = tempfile.mkdtemp(prefix="soro-avaliacao-")
    base = args.porta_base or 18000
    cfg = Namespace(config=args.config, dados=pasta, porta_base=base, intervalo=0.5)
    rede = carregar_rede(cfg)
    resultados = {"intervalo_sincronizacao_s": 0.5, "nos": len(rede.unidades)}
    procs = {}
    print(f"Subindo {len(rede.unidades)} nós em processos separados (dados em {pasta})...")
    try:
        for uid in rede.unidades:
            procs[uid] = iniciar_processo(uid, cfg)
        for u in rede.unidades.values():
            esperar_no(u.url)
        print("Criando as contas da equipe e esperando chegarem a todos os nós...")
        cli = criar_contas(rede)
        enviados = 0

        # 1. Falha de um nó -------------------------------------------------
        polo = next(u for u in rede.unidades.values() if u.nivel == "polo" and u.abastece)
        postos = [rede.unidade(f) for f in polo.abastece]
        print(f"\n[1] Derrubando {polo.nome} e registrando casos nos postos dele...")
        procs[polo.id].terminate()
        procs[polo.id].wait()
        aceitos = sum(_caso(cli[p.id]) for p in postos for _ in range(10))
        enviados += 10 * len(postos)
        print(f"    aceitos com o polo fora do ar: {aceitos} de {10 * len(postos)}")
        procs[polo.id] = iniciar_processo(polo.id, cfg)
        esperar_no(polo.url)
        cli[polo.id].entrar(operador(polo), SENHA_EXEMPLO)  # sessões ficam na memória do nó
        t = _esperar_convergencia(rede, list(rede.unidades))
        print(f"    polo de volta; todos os nós iguais depois de {t:.2f} s" if t else "    não convergiu no tempo-limite")
        resultados["falha_de_no"] = {"polo": polo.id, "casos_enviados": 10 * len(postos),
                                     "aceitos": aceitos, "convergencia_apos_volta_s": t}

        # 2. Dados iguais ----------------------------------------------------
        print("\n[2] Todos os nós registrando ao mesmo tempo...")
        por_no = 20
        threads = [threading.Thread(target=lambda u=u: [_caso(cli[u.id]) for _ in range(por_no)])
                   for u in rede.unidades.values()]
        [th.start() for th in threads]
        [th.join() for th in threads]
        enviados += por_no * len(rede.unidades)
        t = _esperar_convergencia(rede, list(rede.unidades))
        print(f"    {por_no * len(rede.unidades)} casos em {len(rede.unidades)} nós; iguais em {t:.2f} s"
              if t else "    não convergiu no tempo-limite")
        resultados["dados_iguais"] = {"casos": por_no * len(rede.unidades), "convergencia_s": t}

        # 3. Nada se perde -----------------------------------------------------
        print("\n[3] Reenviando casos repetidos e contando...")
        alvo = postos[0]
        ids = [uuid.uuid4().hex for _ in range(10)]
        for cid in ids:
            _caso(cli[alvo.id], cid)
            _caso(cli[alvo.id], cid)  # o mesmo caso de novo, como num reenvio do cliente
        enviados += len(ids)
        _esperar_convergencia(rede, list(rede.unidades))
        casos_por_no = {u.id: obter(u.url + "/api/contagem")["casos"] for u in rede.unidades.values()}
        ok = all(n == enviados for n in casos_por_no.values())
        print(f"    casos distintos enviados: {enviados}; em cada nó: {sorted(set(casos_por_no.values()))}"
              f" -> {'nenhum perdido ou duplicado' if ok else 'DIFERENÇA'}")
        resultados["nada_se_perde"] = {"enviados_distintos": enviados, "reenvios": len(ids),
                                       "casos_por_no": casos_por_no, "ok": ok}
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        for p in procs.values():
            p.wait(timeout=10)

    # 4. Velocidade ---------------------------------------------------------------
    print(f"\n[4] Postos críticos em paralelo (mapa sintético {args.lado}x{args.lado}, {os.cpu_count()} núcleos)...")
    linhas = medir_speedup(args.lado, 200)
    for l in linhas:
        print(f"    {l['processos']:>2} processos: {l['segundos']:>6.2f} s  speedup {l['speedup']:.2f}")
    resultados["velocidade"] = linhas

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultados gravados em {saida}")
