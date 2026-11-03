"""Leitura e validação do arquivo que descreve a rede de um estado.

O arquivo JSON (ver ``redes/amazonas.json``) define as unidades, quem abastece
quem, com quem cada unidade sincroniza, a capacidade da geladeira, o estoque-alvo
e o mapa de localidades e trechos usado para calcular rotas. Para usar o sistema
em outro estado basta escrever outro arquivo nesse formato.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

NIVEIS = ("estado", "polo", "posto")


@dataclass
class Unidade:
    id: str
    nome: str
    nivel: str
    regiao: str | None
    local: str
    porta: int
    capacidade: int
    abastece: list[str]
    vizinhos: list[str]
    alvo: dict[str, int]
    host: str = "127.0.0.1"
    pai: str | None = None
    cnes: str | None = None
    estabelecimento: dict | None = None  # dados do CNES, ver cnes.py

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.porta}"


@dataclass
class Rede:
    estado: str
    soros: dict[str, str]
    agravos: dict[str, dict]
    parametros: dict
    unidades: dict[str, Unidade]
    localidades: dict[str, dict]
    trechos: list[tuple[str, str, float, str]]
    arquivo: str = ""
    regioes: list[str] = field(default_factory=list)

    def unidade(self, uid: str) -> Unidade:
        if uid not in self.unidades:
            raise KeyError(f"unidade desconhecida: {uid}")
        return self.unidades[uid]

    def da_regiao(self, regiao: str) -> list[Unidade]:
        return [u for u in self.unidades.values() if u.regiao == regiao]

    def param(self, nome: str, padrao=None):
        return self.parametros.get(nome, padrao)


def carregar(caminho: str | Path) -> Rede:
    caminho = Path(caminho)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    unidades = {}
    for u in dados["unidades"]:
        unidades[u["id"]] = Unidade(
            id=u["id"], nome=u["nome"], nivel=u["nivel"], regiao=u.get("regiao"),
            local=u["local"], porta=int(u["porta"]), capacidade=int(u["capacidade"]),
            abastece=list(u.get("abastece", [])), vizinhos=list(u.get("vizinhos", [])),
            alvo=dict(u.get("alvo", {})), host=u.get("host", "127.0.0.1"), cnes=u.get("cnes"))
    rede = Rede(
        estado=dados["estado"], soros=dados["soros"], agravos=dados["agravos"],
        parametros=dados.get("parametros", {}), unidades=unidades,
        localidades={l["id"]: l for l in dados["localidades"]},
        trechos=[tuple(t) for t in dados["trechos"]], arquivo=str(caminho))
    _validar_e_completar(rede)
    # Dados dos estabelecimentos baixados do CNES (python -m soro cnes), se já existirem.
    cache = arquivo_cnes(caminho)
    if cache.exists():
        estab = json.loads(cache.read_text(encoding="utf-8"))
        for u in rede.unidades.values():
            u.estabelecimento = estab.get(u.cnes) if u.cnes else None
    return rede


def arquivo_cnes(caminho: str | Path) -> Path:
    caminho = Path(caminho)
    return caminho.with_name(caminho.stem + ".cnes.json")


def _validar_e_completar(rede: Rede) -> None:
    erros = []
    portas = {}
    for u in rede.unidades.values():
        if u.nivel not in NIVEIS:
            erros.append(f"{u.id}: nível '{u.nivel}' inválido (use {', '.join(NIVEIS)})")
        if u.local not in rede.localidades:
            erros.append(f"{u.id}: localidade '{u.local}' não existe")
        if (u.host, u.porta) in portas:
            erros.append(f"{u.id}: porta {u.porta} já usada por {portas[(u.host, u.porta)]}")
        portas[(u.host, u.porta)] = u.id
        for outro in u.abastece + u.vizinhos:
            if outro not in rede.unidades:
                erros.append(f"{u.id}: unidade '{outro}' não existe")
        for soro in u.alvo:
            if soro not in rede.soros:
                erros.append(f"{u.id}: soro '{soro}' não existe")
    for a, b, horas, _ in rede.trechos:
        for loc in (a, b):
            if loc not in rede.localidades:
                erros.append(f"trecho {a}-{b}: localidade '{loc}' não existe")
        if horas <= 0:
            erros.append(f"trecho {a}-{b}: tempo deve ser positivo")
    if erros:
        raise ValueError("Configuração inválida:\n  " + "\n  ".join(erros))

    # Sincronização é sempre nos dois sentidos, então a vizinhança fica simétrica.
    for u in rede.unidades.values():
        for v in u.vizinhos:
            if u.id not in rede.unidades[v].vizinhos:
                rede.unidades[v].vizinhos.append(u.id)
    # Cada unidade tem no máximo um fornecedor (pai).
    for u in rede.unidades.values():
        for filho in u.abastece:
            if rede.unidades[filho].pai not in (None, u.id):
                raise ValueError(f"{filho} é abastecido por mais de uma unidade")
            rede.unidades[filho].pai = u.id
    rede.regioes = sorted({u.regiao for u in rede.unidades.values() if u.regiao})
