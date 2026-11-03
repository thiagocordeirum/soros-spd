"""Sincronização entre vizinhos por anti-entropia (gossip).

A cada intervalo, o nó escolhe um vizinho ao acaso e faz uma troca em duas
etapas (push-pull):

1. envia ``POST /sync`` com o seu vetor de versões e os últimos contatos;
   o vizinho responde com os eventos que faltam ao nó e o vetor dele;
2. o nó grava o que recebeu e envia ``POST /sync/eventos`` com o que falta
   ao vizinho.

Se o vizinho estiver fora do ar, a troca falha e o nó tenta outro na próxima
rodada. Nenhuma operação do usuário espera por isso: a sincronização roda numa
thread separada.
"""
from __future__ import annotations

import json
import random
import threading
import time
import urllib.error
import urllib.request

TEMPO_LIMITE_S = 5.0


def postar(url: str, corpo: dict, tempo_limite: float = TEMPO_LIMITE_S) -> dict:
    dados = json.dumps(corpo, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=dados, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=tempo_limite) as resp:
        return json.loads(resp.read() or b"{}")


class Sincronizador:
    def __init__(self, no, intervalo_s: float = 2.0):
        self.no = no
        self.intervalo = intervalo_s
        self.vizinhos = list(no.u.vizinhos)
        self.situacao = {v: {"ultimo_ok": None, "ultima_falha": None, "erro": None} for v in self.vizinhos}
        self.metricas = {"trocas_ok": 0, "trocas_falhas": 0, "eventos_recebidos": 0,
                         "eventos_enviados": 0, "bytes": 0}
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._laco, name=f"sync-{no.u.id}", daemon=True)
        self._rng = random.Random(no.u.id)

    def iniciar(self) -> None:
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()

    def _laco(self) -> None:
        while not self._parar.wait(self.intervalo * self._rng.uniform(0.6, 1.4)):
            self.no.diario.marcar_contato(self.no.u.id)
            if self.vizinhos:
                self.trocar(self._rng.choice(self.vizinhos))

    def trocar(self, vizinho: str) -> bool:
        """Uma rodada de anti-entropia com ``vizinho``. Devolve True se deu certo."""
        diario = self.no.diario
        url = self.no.rede.unidade(vizinho).url
        try:
            resposta = postar(f"{url}/sync", {"de": self.no.u.id, "vetor": diario.vetor(),
                                              "contatos": diario.contatos()})
            novos = diario.incorporar(resposta.get("eventos", []))
            diario.juntar_contatos(resposta.get("contatos", {}))
            faltam = diario.desde(resposta.get("vetor", {}))
            if faltam:
                postar(f"{url}/sync/eventos", {"de": self.no.u.id, "eventos": faltam,
                                                "contatos": diario.contatos()})
            self.metricas["trocas_ok"] += 1
            self.metricas["eventos_recebidos"] += len(novos)
            self.metricas["eventos_enviados"] += len(faltam)
            self.situacao[vizinho].update({"ultimo_ok": time.time(), "erro": None})
            return True
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.metricas["trocas_falhas"] += 1
            self.situacao[vizinho].update({"ultima_falha": time.time(), "erro": str(getattr(e, "reason", e))})
            return False

    def estado(self) -> dict:
        agora = time.time()
        return {"intervalo_s": self.intervalo, "metricas": dict(self.metricas),
                "vizinhos": [{"id": v, "nome": self.no.rede.unidade(v).nome,
                              "ultimo_ok_ha_s": None if s["ultimo_ok"] is None else round(agora - s["ultimo_ok"], 1),
                              "erro": s["erro"]} for v, s in self.situacao.items()]}
