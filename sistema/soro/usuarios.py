"""Tipos de conta, o que cada um pode fazer e como a senha é guardada.

As contas são eventos do diário como qualquer outro (``usuario`` ao criar,
``usuario_alt`` ao trocar senha ou desativar) e chegam a todos os nós pela
sincronização. Assim, cada nó confere o login sozinho, mesmo sem falar com a
secretaria. A senha nunca é guardada: só o sal e o resultado do PBKDF2.

O cidadão que procura soro não tem conta: a tela dele e as rotas que ela usa
são abertas.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re

ITERACOES = 200_000

# pode: atender (registrar casos), estoque (entradas, perdas, receber remessa, pedir soro),
# enviar (mandar remessa), paineis (painel, sugestões, postos críticos), usuarios (cadastrar contas)
TIPOS = {
    "profissional": {"nome": "Profissional de saúde", "niveis": ["posto", "polo"],
                     "pode": {"atender", "estoque"}},
    "coordenador": {"nome": "Coordenação do polo", "niveis": ["polo"],
                    "pode": {"atender", "estoque", "enviar", "paineis", "usuarios"}},
    "gestor": {"nome": "Gestão estadual", "niveis": ["estado"],
               "pode": {"atender", "estoque", "enviar", "paineis", "usuarios"}},
}

ACOES = {"atender": "registrar atendimentos", "estoque": "mexer no estoque", "enviar": "enviar remessas",
         "paineis": "ver os painéis de gestão", "usuarios": "cadastrar pessoas"}

LOGIN_VALIDO = re.compile(r"^[a-z0-9._-]{3,32}$")
SENHA_MINIMA = 8


def cifrar(senha: str) -> dict:
    sal = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, ITERACOES)
    return {"sal": sal.hex(), "hash": h.hex(), "iter": ITERACOES}


def confere(senha: str, conta: dict) -> bool:
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(conta["sal"]), conta["iter"])
    return hmac.compare_digest(h.hex(), conta["hash"])


def pode(conta: dict, acao: str) -> bool:
    return acao in TIPOS[conta["tipo"]]["pode"]


def unidades_geridas(rede, autor: dict) -> set[str] | None:
    """Unidades cujas contas o autor administra; None quer dizer todas."""
    if autor["tipo"] == "gestor":
        return None
    if autor["tipo"] == "coordenador":
        polo = rede.unidade(autor["unidade"])
        return {polo.id, *polo.abastece}
    return set()


def pode_cadastrar(rede, autor: dict, tipo: str, unidade: str) -> bool:
    if autor["tipo"] == "gestor":
        return True
    # A coordenação cadastra só profissionais do próprio polo e dos postos que ele abastece.
    return tipo == "profissional" and unidade in (unidades_geridas(rede, autor) or set())
