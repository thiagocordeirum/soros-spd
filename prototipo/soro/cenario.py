"""Cenário ilustrativo: calha do Solimões, no Amazonas.

ATENÇÃO: os municípios são reais, mas tempos de viagem, disponibilidade de
enlace, estoques e taxas de acidente são valores ILUSTRATIVOS, escolhidos para
exercitar o sistema -- não são dados oficiais. As comunidades são fictícias.
"""
from __future__ import annotations

from .grafo import GrafoMultimodal

# nome -> (papel, região)
NOS = {
    "Manaus":                ("central", "Central"),
    "Tabatinga":             ("polo",    "Alto Solimões"),
    "Benjamin Constant":     ("posto",   "Alto Solimões"),
    "Atalaia do Norte":      ("posto",   "Alto Solimões"),
    "São Paulo de Olivença": ("posto",   "Alto Solimões"),
    "Tefé":                  ("polo",    "Médio Solimões"),
    "Alvarães":              ("posto",   "Médio Solimões"),
    "Uarini":                ("posto",   "Médio Solimões"),
}
REGIOES = ["Alto Solimões", "Médio Solimões"]

# Enlaces de comunicação (quem sincroniza com quem) e fração do tempo com sinal.
ENLACES = {
    ("Manaus", "Tabatinga"): 0.95,
    ("Manaus", "Tefé"): 0.95,
    ("Tabatinga", "Tefé"): 0.60,
    ("Tabatinga", "Benjamin Constant"): 0.80,
    ("Tabatinga", "Atalaia do Norte"): 0.35,
    ("Benjamin Constant", "Atalaia do Norte"): 0.50,
    ("Tabatinga", "São Paulo de Olivença"): 0.45,
    ("Tefé", "Alvarães"): 0.85,
    ("Tefé", "Uarini"): 0.70,
    ("Alvarães", "Uarini"): 0.40,
}
# Quedas longas: (nó, dia inicial, dia final). Atalaia fica ilhada durante o surto.
QUEDAS = [("Atalaia do Norte", 12.0, 21.0), ("Uarini", 5.0, 9.0)]


def montar_grafo() -> GrafoMultimodal:
    g = GrafoMultimodal()
    for nome, (papel, regiao) in NOS.items():
        g.adicionar_local(nome, papel, regiao)
    trechos = [
        ("Manaus", "Tabatinga", 2.0, "avião"),
        ("Manaus", "Tefé", 1.3, "avião"),
        ("Tabatinga", "Benjamin Constant", 0.5, "voadeira"),
        ("Benjamin Constant", "Atalaia do Norte", 1.0, "estrada"),
        ("Tabatinga", "São Paulo de Olivença", 4.0, "voadeira"),
        ("Tefé", "Alvarães", 0.5, "voadeira"),
        ("Tefé", "Uarini", 1.5, "voadeira"),
        ("São Paulo de Olivença", "Tefé", 14.0, "barco"),
    ]
    comunidades = [
        # (comunidade, região, [(vizinho, horas, modal)])
        ("Aldeia Igarapé Preto", "Alto Solimões", [("Tabatinga", 0.7, "estrada")]),
        ("Comunidade Lago Grande", "Alto Solimões", [("Benjamin Constant", 2.5, "voadeira")]),
        ("Aldeia Rio Itaquaí", "Alto Solimões", [("Atalaia do Norte", 9.0, "barco"), ("Aldeia Alto Ituí", 3.0, "a pé")]),
        ("Aldeia Alto Ituí", "Alto Solimões", [("Atalaia do Norte", 13.0, "barco")]),
        ("Comunidade Santa Clara", "Alto Solimões", [("São Paulo de Olivença", 3.0, "voadeira")]),
        ("Comunidade Boa Vista", "Alto Solimões", [("São Paulo de Olivença", 1.2, "voadeira"), ("Benjamin Constant", 5.0, "barco")]),
        ("Comunidade Caiambé", "Médio Solimões", [("Tefé", 3.5, "voadeira")]),
        ("Comunidade Nogueira", "Médio Solimões", [("Alvarães", 1.0, "voadeira")]),
        ("Comunidade Porto Novo", "Médio Solimões", [("Uarini", 2.0, "voadeira"), ("Alvarães", 2.8, "voadeira")]),
        ("Comunidade Lago Tefé", "Médio Solimões", [("Tefé", 1.8, "rabeta")]),
    ]
    for a, b, h, m in trechos:
        g.adicionar_trecho(a, b, h, m)
    for nome, regiao, _ in comunidades:
        g.adicionar_local(nome, "comunidade", regiao)
    for nome, _, ligacoes in comunidades:
        for viz, h, m in ligacoes:
            g.adicionar_trecho(nome, viz, h, m)
    return g


SOROS = ["SAB", "SABL", "SAEsc", "SAEl"]

# Estoque inicial (ampolas) por tipo de nó.
ESTOQUE_INICIAL = {
    "central": {"SAB": 3000, "SABL": 400, "SAEsc": 300, "SAEl": 80},
    "polo":    {"SAB": 120, "SABL": 40, "SAEsc": 30, "SAEl": 10},
    "posto":   {"SAB": 40, "SABL": 10, "SAEsc": 10, "SAEl": 0},
}
# Capacidade de armazenamento refrigerado (ampolas, todos os soros somados).
# Uma geladeira cheia de outros insumos não comporta mais soro, por isso a
# remessa nunca pode passar do espaço livre do destino.
CAPACIDADE = {"central": 10000, "polo": 400, "posto": 120}
VALIDADE_PADRAO = 365.0
# Um lote vencendo no meio do experimento, para exercitar FEFO e vencimento.
LOTE_VENCENDO = ("Benjamin Constant", "SAB", 20, 10.0)

# Perfil de acidentes (Amazonas): ~90% botrópico entre os ofídicos.
AGRAVOS = [  # (agravo, soro, probabilidade)
    ("botrópico", "SAB", 0.80),
    ("laquético", "SABL", 0.07),
    ("escorpiônico", "SAEsc", 0.09),
    ("elapídico", "SAEl", 0.04),
]
# Substitutos aceitáveis: o antibotrópico-laquético também trata o botrópico.
SUBSTITUTOS = {"SAB": ["SAB", "SABL"]}
GRAVIDADE = [("leve", 0.55), ("moderado", 0.35), ("grave", 0.10)]
AMPOLAS = {  # ampolas por (soro, gravidade) -- valores de referência simplificados
    "SAB": {"leve": 4, "moderado": 8, "grave": 12},
    "SABL": {"leve": 10, "moderado": 10, "grave": 20},
    "SAEsc": {"leve": 0, "moderado": 3, "grave": 6},
    "SAEl": {"leve": 10, "moderado": 10, "grave": 10},
}

TAXA_BASE = 0.35          # casos/dia por posto ou polo
SURTO = ("Alto Solimões", 14, 19, 6.0)   # região, dia inicial, dia final, multiplicador
TEMPO_LIMITE_H = 6.0      # tempo a partir do qual o prognóstico piora
