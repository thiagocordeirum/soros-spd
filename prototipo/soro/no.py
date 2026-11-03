"""Nó do sistema: um posto (PEA), um polo regional ou a central estadual.

Cada nó é autônomo: tem uma réplica completa do estado e atende o paciente
consultando apenas essa réplica, esteja ou não conectado. Periodicamente
escolhe um vizinho e executa uma rodada de anti-entropia push-pull por TCP:
envia o próprio estado, recebe o do vizinho e os dois fazem merge (Demers et
al., 1987). Como o merge é de CRDTs, a ordem e a repetição das rodadas não
importam.

Protocolo: uma linha JSON em cada sentido, ``{"de": nome, "estado": {...}}``.
"""
from __future__ import annotations

import asyncio
import json
import random

from .crdt import EstadoReplica
from .surto import c2, contagens_diarias

HOST = "127.0.0.1"
LIMITE_LINHA = 64 * 1024 * 1024


class No:
    def __init__(self, nome: str, papel: str, regiao: str, porta: int, rede, relogio,
                 portas: dict[str, int], log, intervalo_gossip: float = 0.05):
        self.nome = nome
        self.papel = papel            # "posto" | "polo" | "central"
        self.regiao = regiao
        self.porta = porta
        self.rede = rede
        self.relogio = relogio
        self.portas = portas
        self.log = log
        self.intervalo_gossip = intervalo_gossip
        self.estado = EstadoReplica()
        self.vizinhos = rede.vizinhos(nome)
        self.alertas_recebidos: dict[str, float] = {}   # id -> dia em que chegou aqui
        self.casos_recebidos: dict[str, float] = {}     # id -> dia em que chegou aqui
        self.metricas = {"sync_ok": 0, "sync_sem_enlace": 0, "bytes": 0}
        self._seq = 0
        self._servidor = None
        self._tarefa = None
        self._rng = random.Random(nome)

    # --- ciclo de vida --------------------------------------------------
    async def iniciar(self) -> None:
        self._servidor = await asyncio.start_server(self._atender, HOST, self.porta, limit=LIMITE_LINHA)
        self._tarefa = asyncio.create_task(self._gossip())

    async def parar(self) -> None:
        self._tarefa.cancel()
        self._servidor.close()
        await self._servidor.wait_closed()

    # --- anti-entropia ----------------------------------------------------
    def _mensagem(self) -> bytes:
        return (json.dumps({"de": self.nome, "estado": self.estado.para_dict()},
                           separators=(",", ":")) + "\n").encode()

    async def _atender(self, reader, writer) -> None:
        try:
            msg = json.loads(await reader.readline())
            self._incorporar(EstadoReplica.de_dict(msg["estado"]))
            saida = self._mensagem()
            writer.write(saida)
            await writer.drain()
        finally:
            writer.close()

    async def sincronizar(self, vizinho: str) -> bool:
        if not self.rede.link_ativo(self.nome, vizinho, self.relogio.dia):
            self.metricas["sync_sem_enlace"] += 1
            return False
        reader, writer = await asyncio.open_connection(HOST, self.portas[vizinho], limit=LIMITE_LINHA)
        try:
            saida = self._mensagem()
            writer.write(saida)
            await writer.drain()
            resposta = await reader.readline()
        finally:
            writer.close()
        self._incorporar(EstadoReplica.de_dict(json.loads(resposta)["estado"]))
        self.metricas["sync_ok"] += 1
        self.metricas["bytes"] += len(saida) + len(resposta)
        return True

    async def _gossip(self) -> None:
        while True:
            await asyncio.sleep(self.intervalo_gossip * self._rng.uniform(0.5, 1.5))
            # "Estou vivo e meus dados valem até agora": vai junto na sincronização.
            self.estado.ultimo_contato.atualizar(self.nome, self.relogio.dia)
            if self.vizinhos:
                try:
                    await self.sincronizar(self._rng.choice(self.vizinhos))
                except (ConnectionError, OSError):
                    pass

    def _incorporar(self, remoto: EstadoReplica) -> None:
        novidades = self.estado.merge(remoto)
        dia = self.relogio.dia
        for cid in novidades["casos"]:
            self.casos_recebidos[cid] = dia
        for aid in novidades["alertas"]:
            self._entregar_alerta(self.estado.alertas.registros[aid], dia)

    def _entregar_alerta(self, alerta: dict, dia: float) -> None:
        """Alerta de surto é endereçado à região: só os nós dela o exibem."""
        if alerta["regiao"] != self.regiao and self.papel != "central":
            return
        self.alertas_recebidos[alerta["id"]] = dia
        if self.papel == "posto":
            atraso = dia - alerta["dia_deteccao"]
            self.log(dia, self.nome, f"ALERTA recebido: surto em {alerta['regiao']} "
                     f"({alerta['observado']} casos/dia, limiar {alerta['limiar']:.1f}) "
                     f"-- {atraso:.2f} dia(s) após a detecção")

    # --- operações locais (funcionam offline) -----------------------------
    def notificar_caso(self, caso: dict) -> str:
        self._seq += 1
        cid = f"{self.nome}#{self._seq}"
        self.estado.casos.adicionar(cid, {"id": cid, "posto": self.nome, "regiao": self.regiao, **caso})
        self.casos_recebidos[cid] = caso["dia"]
        return cid

    def dispensar(self, soro: str, ampolas: int) -> int:
        return self.estado.inventario.dispensar(self.nome, self.nome, soro, ampolas, self.relogio.dia)

    def saldo(self, posto: str, soro: str) -> int:
        return self.estado.inventario.saldo(posto, soro, self.relogio.dia)

    def movimentar(self, posto: str, lote: str, qtd: int) -> None:
        self.estado.inventario.movimentar(self.nome, posto, lote, qtd)

    def idade(self, no: str) -> float:
        """Há quantos dias esta réplica não recebe dados novos de ``no``."""
        visto = self.estado.ultimo_contato.get(no)
        return float("inf") if visto is None else max(0.0, self.relogio.dia - visto)

    def estoque_total(self, posto: str) -> int:
        """Ampolas de todos os soros em ``posto``, segundo esta réplica."""
        inv = self.estado.inventario
        soros = {meta["soro"] for meta in inv.lotes.valores()}
        return sum(inv.saldo(posto, s, self.relogio.dia) for s in soros)

    def avaliar_surto(self, regioes: list[str], janela: int = 3) -> list[dict]:
        """Roda o C2 sobre os casos *que este nó conhece* e emite alertas.

        O id do alerta é determinístico (região + semana epidemiológica), então
        se o polo e a central detectarem o mesmo surto, o GSet funde os dois.
        """
        dia = self.relogio.dia
        hoje = int(dia)
        novos = []
        for regiao in regioes:
            ativo = any(a["regiao"] == regiao and hoje - a["dia_referencia"] < 7
                        for a in self.estado.alertas.valores())
            if ativo:
                continue
            contagens = contagens_diarias(self.estado.casos.valores(), regiao)
            for d in range(hoje - janela + 1, hoje + 1):
                alarme, observado, limiar = c2(contagens, d)
                if alarme:
                    alerta = {"id": f"surto:{regiao}:semana{d // 7}", "regiao": regiao,
                              "dia_referencia": d, "dia_deteccao": round(dia, 3),
                              "observado": observado, "limiar": round(limiar, 2),
                              "detectado_por": self.nome}
                    if self.estado.alertas.adicionar(alerta["id"], alerta):
                        self.log(dia, self.nome, f"SURTO detectado em {regiao}: {observado} casos "
                                 f"no dia {d} (limiar C2 = {limiar:.1f}). Alerta emitido.")
                        self._entregar_alerta(alerta, dia)
                        novos.append(alerta)
                    break
        return novos
