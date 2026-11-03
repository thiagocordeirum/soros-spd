"""Demonstração do protótipo: rede de postos de soro com conectividade intermitente.

Sobe 8 nós (central, 2 polos, 5 postos), cada um com seu servidor TCP, e
simula ~30 dias de acidentes, dispensações, remessas, quedas de enlace e um
surto regional. No fim, restabelece todos os enlaces e mede quanto tempo as
réplicas levam para convergir ao mesmo estado.

    python demo.py                 # execução padrão (~15 s)
    python demo.py --verbose       # mostra cada caso atendido
    python demo.py --dias 45 --semente 3
"""
from __future__ import annotations

import argparse
import asyncio
import heapq
import itertools
import math
import os
import random
import statistics
import time

from soro import cenario as C
from soro.grafo import INF, cobertura, criticidade, rota
from soro.no import No
from soro.rede import Rede, Relogio


class Registro:
    def __init__(self, verbose: bool):
        self.verbose = verbose

    def __call__(self, dia: float, quem: str, msg: str, detalhe: bool = False) -> None:
        if detalhe and not self.verbose:
            return
        print(f"[dia {dia:5.2f}] {quem:<22} {msg}")


def poisson(rng: random.Random, lam: float) -> int:
    limite, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def sortear(rng: random.Random, opcoes):
    """Sorteia uma opção de uma lista de tuplas (valor..., probabilidade)."""
    u, acumulado = rng.random(), 0.0
    for *valor, prob in opcoes:
        acumulado += prob
        if u <= acumulado:
            break
    return valor if len(valor) > 1 else valor[0]


class Simulacao:
    def __init__(self, args):
        self.args = args
        self.rng = random.Random(args.semente)
        self.log = Registro(args.verbose)
        self.grafo = C.montar_grafo()
        self.rede = Rede(C.ENLACES, C.QUEDAS, semente=args.semente)
        self.relogio = Relogio(args.seg_por_dia)
        portas = {nome: args.porta_base + i for i, nome in enumerate(C.NOS)}
        self.nos = {nome: No(nome, papel, regiao, portas[nome], self.rede, self.relogio, portas,
                             self.log, intervalo_gossip=args.gossip)
                    for nome, (papel, regiao) in C.NOS.items()}
        self.eventos: list = []
        self._seq = itertools.count()
        self._lotes = itertools.count(1)
        self.ultimo_envio: dict[str, float] = {}
        self.stats = {"casos": 0, "com_soro_local": 0, "sem_soro_necessario": 0, "encaminhados": 0,
                      "encaminhados_sem_soro_no_destino": 0, "sem_destino": 0, "remessas": 0,
                      "ampolas_enviadas": 0, "excedeu_capacidade": 0}
        self.casos_ids: list[str] = []

    # --- agenda de eventos ---------------------------------------------------
    def agendar(self, dia: float, tipo: str, **dados) -> None:
        heapq.heappush(self.eventos, (dia, next(self._seq), tipo, dados))

    def preparar(self) -> None:
        for nome, no in self.nos.items():
            for soro, qtd in C.ESTOQUE_INICIAL[no.papel].items():
                if qtd:
                    lote = f"{soro}-{nome[:3].upper()}-INI"
                    no.estado.inventario.registrar_lote(lote, soro, C.VALIDADE_PADRAO)
                    no.movimentar(nome, lote, qtd)
        posto, soro, qtd, validade = C.LOTE_VENCENDO
        no = self.nos[posto]
        no.estado.inventario.registrar_lote(f"{soro}-VENC-01", soro, validade)
        no.movimentar(posto, f"{soro}-VENC-01", qtd)

        regiao_surto, ini, fim, mult = C.SURTO
        for dia in range(self.args.dias):
            for nome, no in self.nos.items():
                if no.papel == "central":
                    continue
                taxa = C.TAXA_BASE * (mult if no.regiao == regiao_surto and ini <= dia <= fim else 1)
                for _ in range(poisson(self.rng, taxa)):
                    self.agendar(dia + self.rng.random(), "acidente", posto=nome)
            for frac in (0.0, 0.25, 0.5, 0.75):
                self.agendar(dia + frac, "vigilancia")
            self.agendar(dia + 0.5, "reabastecimento")
        for dia in self.args.painel:
            self.agendar(dia, "painel")
        for no_, ini_q, fim_q in C.QUEDAS:
            self.agendar(ini_q, "queda", no=no_, inicio=True)
            self.agendar(fim_q, "queda", no=no_, inicio=False)

    # --- tratadores ------------------------------------------------------------
    def acidente(self, posto: str) -> None:
        no, dia = self.nos[posto], self.relogio.dia
        agravo, soro = sortear(self.rng, C.AGRAVOS)
        gravidade = sortear(self.rng, C.GRAVIDADE)
        ampolas = C.AMPOLAS[soro][gravidade]
        caso = {"dia": round(dia, 3), "agravo": agravo, "gravidade": gravidade,
                "soro_indicado": soro, "ampolas": ampolas}
        self.stats["casos"] += 1
        opcoes = C.SUBSTITUTOS.get(soro, [soro])
        if ampolas == 0:
            self.stats["sem_soro_necessario"] += 1
            caso["desfecho"] = "sem indicação de soro"
        else:
            usado = next((s for s in opcoes if no.saldo(posto, s) >= ampolas), None)
            if usado:
                no.dispensar(usado, ampolas)
                self.stats["com_soro_local"] += 1
                caso["desfecho"] = f"soro local ({usado})"
                self.log(dia, posto, f"caso {agravo}/{gravidade}: {ampolas} amp. de {usado} dispensadas",
                         detalhe=True)
            else:
                caso["desfecho"] = self.encaminhar(no, opcoes, ampolas, agravo, gravidade)
        self.casos_ids.append(no.notificar_caso(caso))

    def encaminhar(self, no: No, opcoes, ampolas, agravo, gravidade) -> str:
        """Sem soro local: consulta a réplica LOCAL (talvez desatualizada) e roteia."""
        dia = self.relogio.dia
        candidatos = {p for p in self.nos if p != no.nome
                      and any(no.saldo(p, s) >= ampolas for s in opcoes)}
        r = rota(self.grafo, no.nome, candidatos)
        if r is None:
            self.stats["sem_destino"] += 1
            self.log(dia, no.nome, f"SEM SORO e nenhum destino conhecido com {ampolas} amp.")
            return "sem destino"
        destino, horas, caminho = r
        trajeto = " -> ".join(f"{loc}" + (f" ({m})" if m else "") for loc, m in caminho)
        self.stats["encaminhados"] += 1
        self.log(dia, no.nome, f"SEM SORO para caso {agravo}/{gravidade}. Encaminhado a {destino} "
                 f"em ~{horas:.1f} h: {trajeto}")
        self.agendar(dia + horas / 24, "chegada_paciente", destino=destino, opcoes=opcoes,
                     ampolas=ampolas, origem=no.nome)
        return f"encaminhado a {destino} ({horas:.1f} h)"

    def chegada_paciente(self, destino, opcoes, ampolas, origem) -> None:
        no, dia = self.nos[destino], self.relogio.dia
        usado = next((s for s in opcoes if no.saldo(destino, s) >= ampolas), None)
        if usado:
            no.dispensar(usado, ampolas)
            self.log(dia, destino, f"paciente vindo de {origem} recebeu {ampolas} amp. de {usado}",
                     detalhe=True)
        else:
            self.stats["encaminhados_sem_soro_no_destino"] += 1
            self.log(dia, destino, f"paciente vindo de {origem} chegou e NÃO havia soro "
                     f"(a réplica de {origem} estava desatualizada)")

    def vigilancia(self) -> None:
        for no in self.nos.values():
            if no.papel == "polo":
                no.avaliar_surto([no.regiao])
            elif no.papel == "central":
                no.avaliar_surto(C.REGIOES)

    def reabastecimento(self) -> None:
        """Hierarquia: a central abastece os polos; cada polo abastece seus postos.

        A decisão usa apenas a visão LOCAL do fornecedor. Se o posto está sem
        comunicação, o fornecedor não percebe o consumo e não reabastece.
        """
        for fornecedor in self.nos.values():
            if fornecedor.papel == "central":
                clientes = [n for n in self.nos.values() if n.papel == "polo"]
            elif fornecedor.papel == "polo":
                clientes = [n for n in self.nos.values() if n.papel == "posto" and n.regiao == fornecedor.regiao]
            else:
                continue
            for cliente in clientes:
                self.avaliar_remessa(fornecedor, cliente)

    def avaliar_remessa(self, fornecedor: No, cliente: No) -> None:
        """Decide uma remessa com a visão LOCAL do fornecedor.

        Duas proteções contra a informação velha:
        - o que já foi enviado e ainda não teve recebimento confirmado conta
          como estoque do cliente (remessa em trânsito);
        - a remessa nunca passa do espaço refrigerado livre no cliente.
        """
        dia = self.relogio.dia
        if dia - self.ultimo_envio.get(cliente.nome, -INF) < 2:
            return
        em_alerta = any(a["regiao"] == cliente.regiao and int(dia) - a["dia_referencia"] < 7
                        for a in fornecedor.estado.alertas.valores())
        for soro in C.SOROS:
            alvo = C.ESTOQUE_INICIAL[cliente.papel][soro] * (2 if em_alerta else 1)
            if alvo == 0:
                continue
            visto = fornecedor.saldo(cliente.nome, soro)
            transito = fornecedor.estado.em_transito(fornecedor.nome, cliente.nome, soro)
            if visto + transito >= alvo * 0.5:
                continue
            ocupado = fornecedor.estoque_total(cliente.nome) + fornecedor.estado.em_transito(fornecedor.nome, cliente.nome)
            livre = C.CAPACIDADE[cliente.papel] - ocupado
            reserva = 0.3 * C.ESTOQUE_INICIAL[fornecedor.papel][soro] if fornecedor.papel == "polo" else 0
            qtd = int(min(alvo - visto - transito, livre, fornecedor.saldo(fornecedor.nome, soro) - reserva))
            if qtd <= 0:
                continue
            r = rota(self.grafo, fornecedor.nome, {cliente.nome})
            prazo = 0.5 + r[1] / 24
            itens = []
            for lote, saldo in fornecedor.estado.inventario.lotes_fefo(fornecedor.nome, soro, dia):
                usar = min(saldo, qtd)
                fornecedor.movimentar(fornecedor.nome, lote, -usar)
                validade = fornecedor.estado.inventario.lotes.registros[lote]["validade"]
                itens.append((lote, validade, usar))
                qtd -= usar
                if qtd == 0:
                    break
            total = sum(q for *_, q in itens)
            rid = f"remessa:{fornecedor.nome}:{next(self._lotes)}"
            fornecedor.estado.remessas.adicionar(rid, {"id": rid, "origem": fornecedor.nome,
                                                       "destino": cliente.nome, "soro": soro,
                                                       "qtd": total, "dia_envio": round(dia, 3)})
            self.agendar(dia + prazo, "chegada_remessa", remessa=rid, destino=cliente.nome,
                         soro=soro, itens=itens)
            self.stats["remessas"] += 1
            self.stats["ampolas_enviadas"] += total
            self.ultimo_envio[cliente.nome] = dia
            idade = fornecedor.idade(cliente.nome)
            self.log(dia, fornecedor.nome, f"remessa de {total} amp. de {soro} para {cliente.nome} "
                     f"(visto: {visto} amp. há {idade:.1f} d; em trânsito: {transito}; "
                     f"espaço livre: {livre}{'; região em ALERTA' if em_alerta else ''}); "
                     f"chega em ~{prazo:.1f} d")

    def chegada_remessa(self, remessa, destino, soro, itens) -> None:
        # A remessa chega fisicamente mesmo sem rede; quem registra a entrada e
        # confirma o recebimento é o destino. A confirmação viaja pelo gossip.
        no, dia = self.nos[destino], self.relogio.dia
        total = sum(q for *_, q in itens)
        if no.estoque_total(destino) + total > C.CAPACIDADE[no.papel]:
            self.stats["excedeu_capacidade"] += 1
            self.log(dia, destino, f"remessa de {total} amp. EXCEDE a capacidade refrigerada")
        for lote, validade, qtd in itens:
            no.estado.inventario.registrar_lote(lote, soro, validade)
            no.movimentar(destino, lote, qtd)
        no.estado.recebimentos.adicionar(remessa, {"remessa": remessa, "dia": round(dia, 3)})
        self.log(dia, destino, f"recebeu remessa: {total} amp. de {soro}", detalhe=True)

    def painel(self) -> None:
        """O que a central enxerga agora: estoque e idade da informação de cada nó."""
        central, dia = self.nos["Manaus"], self.relogio.dia
        print(f"\n--- Painel da central no dia {dia:.1f}: o que Manaus sabe agora ---")
        print(f"    {'nó':<22} {'SAB':>5} {'total/capac.':>13}  {'informação de':>14}")
        for nome, no in self.nos.items():
            if no.papel == "central":
                continue
            idade = central.idade(nome)
            quando = "agora" if idade < 0.25 else f"há {idade * 24:.0f} h" if idade < 2 else f"há {idade:.1f} dias"
            alerta = "  <-- desatualizado" if idade >= 2 else ""
            print(f"    {nome:<22} {central.saldo(nome, 'SAB'):>5} "
                  f"{central.estoque_total(nome):>6}/{C.CAPACIDADE[no.papel]:<6}  {quando:>14}{alerta}")
        print()

    def queda(self, no, inicio) -> None:
        estado = "PERDEU a comunicação (queda prolongada)" if inicio else "comunicação restabelecida"
        self.log(self.relogio.dia, no, estado)

    # --- execução -------------------------------------------------------------
    async def executar(self) -> None:
        self.preparar()
        for no in self.nos.values():
            await no.iniciar()
        self.relogio.inicio = time.monotonic()
        print(f"{len(self.nos)} nós no ar (TCP 127.0.0.1:{self.args.porta_base}-"
              f"{self.args.porta_base + len(self.nos) - 1}); simulando {self.args.dias} dias "
              f"({self.args.seg_por_dia} s por dia)\n")
        while self.eventos:
            dia, _, tipo, dados = heapq.heappop(self.eventos)
            espera = dia - self.relogio.dia
            if espera > 0:
                await asyncio.sleep(espera * self.relogio.segundos_por_dia)
            getattr(self, tipo)(**dados)
        await asyncio.sleep(max(0.0, self.args.dias - self.relogio.dia) * self.relogio.segundos_por_dia)

        print("\n--- Fim do período simulado: todos os enlaces restabelecidos ---")
        self.rede.normalizar()
        inicio = time.monotonic()
        while len({no.estado.resumo() for no in self.nos.values()}) > 1:
            if time.monotonic() - inicio > 30:
                break
            await asyncio.sleep(0.01)
        convergencia = time.monotonic() - inicio
        for no in self.nos.values():
            await no.parar()
        self.relatorio(convergencia)

    def relatorio(self, convergencia: float) -> None:
        central = self.nos["Manaus"]
        resumos = {no.estado.resumo() for no in self.nos.values()}
        s = self.stats
        print(f"\n=== CONVERGÊNCIA ===")
        print(f"Réplicas idênticas: {'SIM' if len(resumos) == 1 else 'NÃO'} "
              f"(resumo {next(iter(resumos)) if len(resumos) == 1 else resumos}) "
              f"em {convergencia * 1000:.0f} ms após a normalização da rede")
        sync_ok = sum(n.metricas["sync_ok"] for n in self.nos.values())
        sem = sum(n.metricas["sync_sem_enlace"] for n in self.nos.values())
        mb = sum(n.metricas["bytes"] for n in self.nos.values()) / 1e6
        print(f"Rodadas de anti-entropia: {sync_ok} com sucesso, {sem} sem enlace "
              f"({100 * sem / max(1, sync_ok + sem):.0f}% das tentativas); {mb:.1f} MB trafegados")

        print(f"\n=== ATENDIMENTO ===")
        print(f"Casos: {s['casos']} | com soro no próprio posto: {s['com_soro_local']} | "
              f"sem indicação de soro: {s['sem_soro_necessario']} | encaminhados: {s['encaminhados']} "
              f"(chegaram e não havia soro: {s['encaminhados_sem_soro_no_destino']}) | "
              f"sem destino: {s['sem_destino']}")
        pendentes = sum(1 for rid in central.estado.remessas.registros if rid not in central.estado.recebimentos)
        print(f"Remessas: {s['remessas']} ({s['ampolas_enviadas']} ampolas) | acima da capacidade "
              f"refrigerada: {s['excedeu_capacidade']} | ainda sem confirmação: {pendentes}")

        print(f"\n=== NOTIFICAÇÃO STORE-AND-FORWARD (atraso até a central) ===")
        por_posto: dict[str, list[float]] = {}
        for cid in self.casos_ids:
            caso = central.estado.casos.registros[cid]
            atraso_h = (central.casos_recebidos[cid] - caso["dia"]) * 24
            por_posto.setdefault(caso["posto"], []).append(atraso_h)
        todos = [a for v in por_posto.values() for a in v]
        print(f"Todas as {len(todos)} notificações chegaram (nenhuma perdida). "
              f"Atraso mediano {statistics.median(todos):.1f} h, máximo {max(todos):.1f} h")
        for posto, atrasos in sorted(por_posto.items(), key=lambda kv: -max(kv[1])):
            print(f"  {posto:<22} {len(atrasos):3d} casos  mediana {statistics.median(atrasos):6.1f} h"
                  f"   máx {max(atrasos):6.1f} h")

        print(f"\n=== ALERTAS DE SURTO (entrega aos nós da região) ===")
        for alerta in sorted(central.estado.alertas.valores(), key=lambda a: a["dia_deteccao"]):
            print(f"{alerta['id']}: detectado por {alerta['detectado_por']} no dia "
                  f"{alerta['dia_deteccao']:.2f} ({alerta['observado']} casos > limiar {alerta['limiar']})")
            for no in self.nos.values():
                if no.regiao == alerta["regiao"]:
                    chegou = no.alertas_recebidos.get(alerta["id"])
                    atraso = f"{(chegou - alerta['dia_deteccao']) * 24:6.1f} h" if chegou is not None else "não recebeu"
                    print(f"  {no.nome:<22} {atraso}")

        dia = self.relogio.dia
        inv = central.estado.inventario
        print(f"\n=== ESTOQUE CONVERGIDO (ampolas) ===")
        print(f"  {'nó':<22} {'SAB':>5} {'SABL':>5} {'total/capacidade':>17}")
        for nome, no in self.nos.items():
            print(f"  {nome:<22} {inv.saldo(nome, 'SAB', dia):5d} {inv.saldo(nome, 'SABL', dia):5d} "
                  f"{central.estoque_total(nome):>10}/{C.CAPACIDADE[no.papel]}")
        negativos = inv.saldos_negativos()
        print(f"Saldos negativos (violação de invariante): {negativos or 'nenhum'}")

        print(f"\n=== COBERTURA DE SAB (estado final) ===")
        com_sab = {p for p in self.nos if inv.saldo(p, "SAB", dia) > 0}
        for comunidade, (posto, horas) in sorted(cobertura(self.grafo, com_sab).items(), key=lambda kv: -kv[1][1]):
            marca = "  <-- acima de 6 h" if horas > C.TEMPO_LIMITE_H else ""
            print(f"  {comunidade:<24} {horas:5.1f} h até {posto}{marca}")

        print(f"\n=== CRITICIDADE N-1 (se o posto zerar SAB, quantas comunidades hoje cobertas passam de 6 h) ===")
        trab = self.args.trabalhadores
        crit = criticidade(self.grafo, com_sab, C.TEMPO_LIMITE_H, trabalhadores=trab)
        for posto, n in sorted(crit.items(), key=lambda kv: -kv[1]):
            print(f"  {posto:<22} {n}")
        print(f"(calculado com {trab} processo(s); veja bench_paralelo.py para o ganho em grafos grandes)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dias", type=int, default=30)
    p.add_argument("--seg-por-dia", type=float, default=0.4, help="segundos reais por dia simulado")
    p.add_argument("--gossip", type=float, default=0.05, help="intervalo médio de anti-entropia (s)")
    p.add_argument("--semente", type=int, default=7)
    p.add_argument("--porta-base", type=int, default=47100)
    p.add_argument("--trabalhadores", type=int, default=min(4, os.cpu_count() or 1))
    p.add_argument("--painel", type=float, nargs="*", default=[18.0],
                   help="dias em que se imprime o painel da central (idade da informação)")
    p.add_argument("--verbose", "-v", action="store_true")
    asyncio.run(Simulacao(p.parse_args()).executar())


if __name__ == "__main__":
    main()
