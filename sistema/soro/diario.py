"""Diário de eventos replicado, gravado em SQLite.

Todo dado do sistema é um evento imutável: uma entrada de lote, uma saída, um
caso, uma remessa. Cada evento nasce em uma unidade (a ``origem``) e recebe um
número de sequência local (``seq``) 1, 2, 3... O conjunto de eventos que um nó
conhece é resumido por um vetor de versões ``{origem: maior seq}``.

Por que isso converge sem conflito:

* eventos nunca mudam depois de criados, então juntar dois diários é fazer a
  união dos conjuntos (comutativa, associativa e idempotente, como um G-Set);
* o estado (estoque, casos, alertas) é calculado a partir do conjunto, por
  somas e contagens que não dependem da ordem dos eventos;
* cada nó só aceita o evento ``seq`` de uma origem depois de ter o ``seq - 1``.
  Assim todo nó guarda, para cada origem, um prefixo contínuo 1..n, e o vetor
  de versões descreve exatamente o que ele tem. Na sincronização basta pedir
  "tudo de A depois do 37", sem listar evento por evento.

O relógio de parede (``quando``) é guardado só para exibição e estatística;
nenhuma regra de junção depende dele.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    origem TEXT NOT NULL,
    seq    INTEGER NOT NULL,
    tipo   TEXT NOT NULL,
    chave  TEXT NOT NULL,
    dados  TEXT NOT NULL,
    quando REAL NOT NULL,
    PRIMARY KEY (origem, seq)
);
CREATE INDEX IF NOT EXISTS eventos_tipo ON eventos (tipo);
CREATE INDEX IF NOT EXISTS eventos_chave ON eventos (tipo, chave);
CREATE TABLE IF NOT EXISTS contato (
    unidade TEXT PRIMARY KEY,
    quando  REAL NOT NULL
);
"""


class Diario:
    """Diário de um nó. Seguro para uso por várias threads."""

    def __init__(self, caminho: str | Path, origem: str):
        self.origem = origem
        self._trava = threading.RLock()
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(caminho), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(ESQUEMA)
        self.versao = 0  # muda a cada evento novo; serve para invalidar caches

    # --- escrita local ------------------------------------------------------
    def acrescentar(self, tipo: str, chave: str, dados: dict, quando: float | None = None) -> dict:
        """Cria um evento desta unidade. A gravação é confirmada no disco antes de retornar."""
        quando = time.time() if quando is None else quando
        with self._trava:
            seq = self._ultimo_seq(self.origem) + 1
            self._db.execute("INSERT INTO eventos VALUES (?,?,?,?,?,?)",
                             (self.origem, seq, tipo, chave, _json(dados), quando))
            self.versao += 1
        return {"origem": self.origem, "seq": seq, "tipo": tipo, "chave": chave, "dados": dados, "quando": quando}

    # --- sincronização ------------------------------------------------------
    def vetor(self) -> dict[str, int]:
        with self._trava:
            return {o: s for o, s in self._db.execute("SELECT origem, MAX(seq) FROM eventos GROUP BY origem")}

    def desde(self, vetor_outro: dict[str, int], limite: int = 5000) -> list[dict]:
        """Eventos que o dono de ``vetor_outro`` ainda não tem, em ordem de seq por origem."""
        saida = []
        with self._trava:
            for origem, maximo in self.vetor().items():
                a_partir = int(vetor_outro.get(origem, 0))
                if maximo <= a_partir:
                    continue
                linhas = self._db.execute(
                    "SELECT origem, seq, tipo, chave, dados, quando FROM eventos "
                    "WHERE origem=? AND seq>? ORDER BY seq LIMIT ?", (origem, a_partir, limite))
                saida.extend(_linha_evento(l) for l in linhas)
        return saida

    def incorporar(self, eventos: list[dict]) -> list[dict]:
        """Junta eventos recebidos de outro nó numa única transação.

        Aceita só eventos que continuam o prefixo de cada origem; os demais
        (repetidos ou com buraco antes) são ignorados e voltam numa próxima troca.
        Devolve os eventos que eram novos.
        """
        novos = []
        with self._trava:
            self._db.execute("BEGIN")
            try:
                proximo: dict[str, int] = {}
                for ev in sorted(eventos, key=lambda e: (e["origem"], int(e["seq"]))):
                    o, s = ev["origem"], int(ev["seq"])
                    if o not in proximo:
                        proximo[o] = self._ultimo_seq(o) + 1
                    if s != proximo[o]:
                        continue
                    self._db.execute("INSERT INTO eventos VALUES (?,?,?,?,?,?)",
                                     (o, s, ev["tipo"], ev["chave"], _json(ev["dados"]), float(ev["quando"])))
                    proximo[o] = s + 1
                    novos.append(ev)
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            if novos:
                self.versao += 1
        return novos

    # --- consulta -----------------------------------------------------------
    def eventos(self, tipo: str | None = None) -> list[dict]:
        with self._trava:
            if tipo is None:
                linhas = self._db.execute("SELECT origem, seq, tipo, chave, dados, quando FROM eventos ORDER BY origem, seq")
            else:
                linhas = self._db.execute("SELECT origem, seq, tipo, chave, dados, quando FROM eventos "
                                          "WHERE tipo=? ORDER BY origem, seq", (tipo,))
            return [_linha_evento(l) for l in linhas]

    def existe(self, tipo: str, chave: str) -> bool:
        with self._trava:
            return self._db.execute("SELECT 1 FROM eventos WHERE tipo=? AND chave=? LIMIT 1",
                                    (tipo, chave)).fetchone() is not None

    def total(self) -> int:
        with self._trava:
            return self._db.execute("SELECT COUNT(*) FROM eventos").fetchone()[0]

    def resumo(self) -> str:
        """Hash do conjunto de eventos. Nós com os mesmos eventos têm o mesmo resumo."""
        h = hashlib.sha256()
        with self._trava:
            for o, s, t, c, d, q in self._db.execute(
                    "SELECT origem, seq, tipo, chave, dados, quando FROM eventos ORDER BY origem, seq"):
                h.update(f"{o}\x1f{s}\x1f{t}\x1f{c}\x1f{d}\x1f{q!r}\x1e".encode())
        return h.hexdigest()[:16]

    # --- último contato (idade da informação) --------------------------------
    def marcar_contato(self, unidade: str, quando: float | None = None) -> None:
        self.juntar_contatos({unidade: time.time() if quando is None else quando})

    def juntar_contatos(self, contatos: dict[str, float]) -> None:
        """Registrador de máximo: para cada unidade fica o instante mais recente conhecido."""
        with self._trava:
            for unidade, quando in contatos.items():
                self._db.execute(
                    "INSERT INTO contato VALUES (?,?) ON CONFLICT(unidade) "
                    "DO UPDATE SET quando=MAX(quando, excluded.quando)", (unidade, float(quando)))

    def contatos(self) -> dict[str, float]:
        with self._trava:
            return dict(self._db.execute("SELECT unidade, quando FROM contato"))

    def fechar(self) -> None:
        with self._trava:
            self._db.close()

    def _ultimo_seq(self, origem: str) -> int:
        linha = self._db.execute("SELECT MAX(seq) FROM eventos WHERE origem=?", (origem,)).fetchone()
        return linha[0] or 0


def _json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _linha_evento(l) -> dict:
    o, s, t, c, d, q = l
    return {"origem": o, "seq": s, "tipo": t, "chave": c, "dados": json.loads(d), "quando": q}
