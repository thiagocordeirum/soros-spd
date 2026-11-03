"""Tipos de dados replicados livres de conflito (CRDTs) baseados em estado.

Todo ``merge`` deste módulo é comutativo, associativo e idempotente. Assim,
duas réplicas que receberam o mesmo conjunto de atualizações -- em qualquer
ordem, com repetições e depois de qualquer período de partição -- chegam ao
mesmo estado, sem coordenação e sem servidor central (consistência eventual
forte; Shapiro et al., 2011).
"""
from __future__ import annotations

import hashlib
import json


class GCounter:
    """Contador que só cresce. Cada réplica incrementa apenas a própria posição."""

    def __init__(self, contagens: dict[str, int] | None = None):
        self.contagens: dict[str, int] = dict(contagens or {})

    def incrementar(self, replica: str, n: int = 1) -> None:
        if n < 0:
            raise ValueError("GCounter aceita apenas incrementos não negativos")
        self.contagens[replica] = self.contagens.get(replica, 0) + n

    @property
    def valor(self) -> int:
        return sum(self.contagens.values())

    def merge(self, outro: "GCounter") -> None:
        for replica, v in outro.contagens.items():
            if replica not in self.contagens or v > self.contagens[replica]:
                self.contagens[replica] = v

    def para_dict(self) -> dict[str, int]:
        return dict(self.contagens)


class PNCounter:
    """Contador que aceita somas e subtrações: dois GCounters (P - N)."""

    def __init__(self, p: dict | None = None, n: dict | None = None):
        self.p = GCounter(p)
        self.n = GCounter(n)

    def somar(self, replica: str, qtd: int) -> None:
        if qtd >= 0:
            self.p.incrementar(replica, qtd)
        else:
            self.n.incrementar(replica, -qtd)

    @property
    def valor(self) -> int:
        return self.p.valor - self.n.valor

    def merge(self, outro: "PNCounter") -> None:
        self.p.merge(outro.p)
        self.n.merge(outro.n)

    def para_dict(self) -> dict:
        return {"p": self.p.para_dict(), "n": self.n.para_dict()}


class GSetRegistros:
    """Conjunto que só cresce de registros imutáveis, indexados por id.

    Serve para notificações de caso e alertas de surto: um registro criado
    offline entra no conjunto local e se espalha por anti-entropia até chegar
    a todos (store-and-forward). Reentregas são inofensivas (idempotência).
    Se dois registros com o mesmo id divergirem, vence o menor na forma
    canônica, para que todas as réplicas escolham o mesmo.
    """

    def __init__(self, registros: dict[str, dict] | None = None):
        self.registros: dict[str, dict] = dict(registros or {})

    def adicionar(self, rid: str, registro: dict) -> bool:
        return self._incorporar(rid, registro)

    def _incorporar(self, rid: str, registro: dict) -> bool:
        atual = self.registros.get(rid)
        if atual is None:
            self.registros[rid] = registro
            return True
        if _canonico(registro) < _canonico(atual):
            self.registros[rid] = registro
        return False

    def merge(self, outro: "GSetRegistros") -> list[str]:
        """Incorpora ``outro`` e devolve os ids que eram desconhecidos."""
        return [rid for rid, reg in outro.registros.items() if self._incorporar(rid, reg)]

    def __contains__(self, rid: str) -> bool:
        return rid in self.registros

    def __len__(self) -> int:
        return len(self.registros)

    def valores(self):
        return self.registros.values()

    def para_dict(self) -> dict:
        return dict(self.registros)


class Inventario:
    """Estoque de soro por posto e por lote.

    O saldo de cada par (posto, lote) é um PNCounter: entradas somam,
    dispensações, descartes e transferências subtraem. Os metadados do lote
    (tipo de soro, validade) são imutáveis e ficam num GSet.

    Observação: o CRDT garante convergência, não invariantes. Se duas réplicas
    isoladas dispensarem o mesmo frasco, o saldo convergido fica negativo --
    o que é detectado e reportado, não escondido (ver ``saldos_negativos``).
    """

    def __init__(self):
        self.saldos: dict[str, PNCounter] = {}
        self.lotes = GSetRegistros()

    @staticmethod
    def _chave(posto: str, lote: str) -> str:
        return f"{posto}|{lote}"

    def registrar_lote(self, lote: str, soro: str, validade: float) -> None:
        self.lotes.adicionar(lote, {"soro": soro, "validade": validade})

    def movimentar(self, replica: str, posto: str, lote: str, qtd: int) -> None:
        if lote not in self.lotes:
            raise KeyError(f"lote desconhecido: {lote}")
        self.saldos.setdefault(self._chave(posto, lote), PNCounter()).somar(replica, qtd)

    def saldo_lote(self, posto: str, lote: str) -> int:
        c = self.saldos.get(self._chave(posto, lote))
        return c.valor if c else 0

    def lotes_fefo(self, posto: str, soro: str, dia: float) -> list[tuple[str, int]]:
        """Lotes válidos com saldo, do que vence primeiro ao que vence por último."""
        disponiveis = []
        for chave, contador in self.saldos.items():
            p, lote = chave.split("|", 1)
            meta = self.lotes.registros[lote]
            if p == posto and meta["soro"] == soro and meta["validade"] > dia and contador.valor > 0:
                disponiveis.append((meta["validade"], lote, contador.valor))
        return [(lote, saldo) for _, lote, saldo in sorted(disponiveis)]

    def saldo(self, posto: str, soro: str, dia: float) -> int:
        return sum(s for _, s in self.lotes_fefo(posto, soro, dia))

    def dispensar(self, replica: str, posto: str, soro: str, qtd: int, dia: float) -> int:
        """Baixa ``qtd`` ampolas seguindo FEFO. Devolve quantas foram baixadas."""
        restante = qtd
        for lote, saldo in self.lotes_fefo(posto, soro, dia):
            usar = min(saldo, restante)
            self.movimentar(replica, posto, lote, -usar)
            restante -= usar
            if restante == 0:
                break
        return qtd - restante

    def postos(self) -> set[str]:
        return {chave.split("|", 1)[0] for chave in self.saldos}

    def saldos_negativos(self) -> list[tuple[str, str, int]]:
        return [(*k.split("|", 1), c.valor) for k, c in self.saldos.items() if c.valor < 0]

    def merge(self, outro: "Inventario") -> None:
        self.lotes.merge(outro.lotes)
        for chave, contador in outro.saldos.items():
            self.saldos.setdefault(chave, PNCounter()).merge(contador)

    def para_dict(self) -> dict:
        return {
            "saldos": {k: c.para_dict() for k, c in self.saldos.items()},
            "lotes": self.lotes.para_dict(),
        }

    @classmethod
    def de_dict(cls, d: dict) -> "Inventario":
        inv = cls()
        inv.lotes = GSetRegistros(d["lotes"])
        inv.saldos = {k: PNCounter(v["p"], v["n"]) for k, v in d["saldos"].items()}
        return inv


class MapaMaximo:
    """Mapa chave -> número em que o merge fica com o maior valor de cada chave.

    Usado como "último contato": cada nó escreve só a própria chave com o
    instante atual, e o maior valor visto diz até quando os dados daquele nó
    estão refletidos nesta réplica -- isto é, a idade da informação.
    """

    def __init__(self, valores: dict[str, float] | None = None):
        self.valores: dict[str, float] = dict(valores or {})

    def atualizar(self, chave: str, valor: float) -> None:
        if valor > self.valores.get(chave, float("-inf")):
            self.valores[chave] = valor

    def get(self, chave: str, padrao=None):
        return self.valores.get(chave, padrao)

    def merge(self, outro: "MapaMaximo") -> None:
        for chave, valor in outro.valores.items():
            self.atualizar(chave, valor)

    def para_dict(self) -> dict[str, float]:
        return dict(self.valores)


class EstadoReplica:
    """Tudo o que um nó replica.

    - inventário por (posto, lote);
    - notificações de caso e alertas de surto;
    - remessas despachadas e confirmações de recebimento: uma remessa sem
      confirmação está "em trânsito" para quem a enviou;
    - último contato de cada nó, para mostrar a idade da informação.
    """

    def __init__(self):
        self.inventario = Inventario()
        self.casos = GSetRegistros()
        self.alertas = GSetRegistros()
        self.remessas = GSetRegistros()
        self.recebimentos = GSetRegistros()
        self.ultimo_contato = MapaMaximo()

    def merge(self, outro: "EstadoReplica") -> dict[str, list[str]]:
        self.inventario.merge(outro.inventario)
        self.remessas.merge(outro.remessas)
        self.recebimentos.merge(outro.recebimentos)
        self.ultimo_contato.merge(outro.ultimo_contato)
        return {
            "casos": self.casos.merge(outro.casos),
            "alertas": self.alertas.merge(outro.alertas),
        }

    def em_transito(self, origem: str, destino: str, soro: str | None = None) -> int:
        """Ampolas enviadas de ``origem`` a ``destino`` ainda sem confirmação de recebimento."""
        return sum(r["qtd"] for rid, r in self.remessas.registros.items()
                   if r["origem"] == origem and r["destino"] == destino
                   and (soro is None or r["soro"] == soro) and rid not in self.recebimentos)

    def para_dict(self) -> dict:
        return {
            "inventario": self.inventario.para_dict(),
            "casos": self.casos.para_dict(),
            "alertas": self.alertas.para_dict(),
            "remessas": self.remessas.para_dict(),
            "recebimentos": self.recebimentos.para_dict(),
            "ultimo_contato": self.ultimo_contato.para_dict(),
        }

    @classmethod
    def de_dict(cls, d: dict) -> "EstadoReplica":
        e = cls()
        e.inventario = Inventario.de_dict(d["inventario"])
        e.casos = GSetRegistros(d["casos"])
        e.alertas = GSetRegistros(d["alertas"])
        e.remessas = GSetRegistros(d["remessas"])
        e.recebimentos = GSetRegistros(d["recebimentos"])
        e.ultimo_contato = MapaMaximo(d["ultimo_contato"])
        return e

    def resumo(self) -> str:
        """Hash do estado: réplicas convergidas têm o mesmo resumo.

        O último contato fica de fora: cada nó o atualiza continuamente, então
        ele nunca para de mudar enquanto o sistema está no ar.
        """
        dados = self.para_dict()
        del dados["ultimo_contato"]
        return hashlib.sha256(_canonico(dados).encode()).hexdigest()[:12]


def _canonico(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
