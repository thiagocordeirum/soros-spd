"""Linha de comando.

    python -m soro rede                 # sobe todos os nós da rede, um processo por nó
    python -m soro no tabatinga         # sobe só um nó (por exemplo, em outro computador)
    python -m soro exemplo              # carrega dados de exemplo na rede que está rodando
    python -m soro avaliar              # mede as quatro perguntas da avaliação
    python -m soro speedup              # mede só o ganho do paralelismo

Todas aceitam ``--config`` (padrão: redes/amazonas.json).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PADRAO = RAIZ / "redes" / "amazonas.json"


def carregar_rede(args):
    from .config import carregar
    rede = carregar(args.config)
    if getattr(args, "porta_base", None):
        for i, u in enumerate(rede.unidades.values()):
            u.porta = args.porta_base + i
    return rede


def cmd_no(args):
    from .no import No
    from .servidor import ServidorNo
    rede = carregar_rede(args)
    no = No(rede, args.unidade, args.dados)
    servidor = ServidorNo(no, intervalo_sync=args.intervalo, host=args.escutar)
    print(f"{no.u.nome} ({no.u.nivel}) em {no.u.url}  vizinhos: {', '.join(no.u.vizinhos)}", flush=True)
    def ao_terminar(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, ao_terminar)
    try:
        servidor.iniciar(bloquear=True)
    except KeyboardInterrupt:
        pass
    finally:
        servidor.parar()


def iniciar_processo(uid: str, args) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "soro", "no", uid, "--config", str(args.config), "--dados", str(args.dados)]
    if args.porta_base:
        cmd += ["--porta-base", str(args.porta_base)]
    if args.intervalo:
        cmd += ["--intervalo", str(args.intervalo)]
    env = {**os.environ, "PYTHONPATH": str(RAIZ)}
    return subprocess.Popen(cmd, cwd=RAIZ, env=env)


def esperar_no(url: str, tempo_limite: float = 15.0) -> None:
    fim = time.time() + tempo_limite
    while time.time() < fim:
        try:
            urllib.request.urlopen(f"{url}/api/info", timeout=1).read()
            return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"nó em {url} não respondeu")


def porta_ocupada(host: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, porta)) == 0


def cmd_rede(args):
    rede = carregar_rede(args)
    # Sem esta checagem, um nó antigo ainda no ar responderia no lugar do novo.
    ocupadas = [f"{u.porta} ({u.id})" for u in rede.unidades.values() if porta_ocupada(u.host, u.porta)]
    if ocupadas:
        sys.exit("Portas já em uso: " + ", ".join(ocupadas) + "\nOutra rede está rodando? Pare-a antes "
                 "(Ctrl+C no terminal dela) ou use --porta-base com outro valor.")
    def ao_terminar(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, ao_terminar)
    procs = {uid: iniciar_processo(uid, args) for uid in rede.unidades}
    try:
        for u in rede.unidades.values():
            esperar_no(u.url)
    except (TimeoutError, KeyboardInterrupt) as erro:
        for p in procs.values():
            p.terminate()
        sys.exit(f"A rede não subiu: {erro}")
    print("\nRede no ar. Abra no navegador:")
    for u in rede.unidades.values():
        print(f"  {u.url:<24} {u.nome} ({u.nivel})")
    print(f"\nPágina do cidadão (qualquer nó): {next(iter(rede.unidades.values())).url}/usuario.html")
    print("Ctrl+C para parar todos os nós.\n", flush=True)
    avisados = set()
    try:
        while True:
            for uid, p in procs.items():
                if p.poll() is not None and uid not in avisados:
                    print(f"[aviso] nó {uid} parou (código {p.returncode})", flush=True)
                    avisados.add(uid)
            if len(avisados) == len(procs):
                print("Todos os nós pararam.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nParando...")
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        for p in procs.values():
            p.wait(timeout=10)


def cmd_exemplo(args):
    from .exemplo import carregar_exemplo
    carregar_exemplo(carregar_rede(args), semente=args.semente)


def cmd_cnes(args):
    from .cnes import importar
    importar(carregar_rede(args))


def cmd_avaliar(args):
    from .avaliacao import avaliar
    avaliar(args)


def cmd_speedup(args):
    from .rotas import medir_speedup
    print(f"Mapa sintético {args.lado}x{args.lado}, {args.postos} postos; {os.cpu_count()} núcleos lógicos")
    print(f"{'processos':>9} {'tempo (s)':>10} {'speedup':>8} {'eficiência':>11}")
    for l in medir_speedup(args.lado, args.postos):
        print(f"{l['processos']:>9} {l['segundos']:>10.2f} {l['speedup']:>8.2f} {l['eficiencia']:>10.0%}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m soro", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)

    def comuns(sp, dados=True):
        sp.add_argument("--config", default=str(CONFIG_PADRAO), help="arquivo da rede do estado")
        sp.add_argument("--porta-base", type=int, help="renumera as portas a partir deste valor")
        if dados:
            sp.add_argument("--dados", default=str(RAIZ / "dados"), help="pasta dos bancos SQLite")
            sp.add_argument("--intervalo", type=float, help="segundos entre sincronizações")

    s = sub.add_parser("no", help="sobe um nó")
    s.add_argument("unidade")
    s.add_argument("--escutar", help="endereço de escuta (ex.: 0.0.0.0 para aceitar outras máquinas)")
    comuns(s)
    s.set_defaults(func=cmd_no)

    s = sub.add_parser("rede", help="sobe todos os nós, um processo por nó")
    comuns(s)
    s.set_defaults(func=cmd_rede)

    s = sub.add_parser("exemplo", help="carrega dados de exemplo na rede em execução")
    comuns(s, dados=False)
    s.add_argument("--semente", type=int, default=7)
    s.set_defaults(func=cmd_exemplo)

    s = sub.add_parser("cnes", help="baixa nome, endereço, telefone e coordenadas das unidades no CNES")
    comuns(s, dados=False)
    s.set_defaults(func=cmd_cnes)

    s = sub.add_parser("avaliar", help="sobe uma rede temporária e mede as quatro perguntas")
    comuns(s, dados=False)
    s.add_argument("--saida", default=str(RAIZ / "resultados" / "avaliacao.json"))
    s.add_argument("--lado", type=int, default=120, help="tamanho do mapa sintético do teste de paralelismo")
    s.set_defaults(func=cmd_avaliar)

    s = sub.add_parser("speedup", help="mede o ganho do cálculo de postos críticos em paralelo")
    s.add_argument("--lado", type=int, default=150)
    s.add_argument("--postos", type=int, default=200)
    s.set_defaults(func=cmd_speedup)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
