"""Relógio simulado e modelo de conectividade intermitente.

Os nós conversam por TCP de verdade; o que é simulado é *quando* um enlace
existe. Cada enlace tem uma disponibilidade (fração das janelas de 6 h em
que há sinal -- p. ex. internet via satélite que só funciona com gerador
ligado) e pode sofrer quedas longas programadas (falta de combustível,
equipamento quebrado, cheia).
"""
from __future__ import annotations

import random
import time


class Relogio:
    """Converte tempo real em dias simulados."""

    def __init__(self, segundos_por_dia: float):
        self.segundos_por_dia = segundos_por_dia
        self.inicio = time.monotonic()

    @property
    def dia(self) -> float:
        return (time.monotonic() - self.inicio) / self.segundos_por_dia


class Rede:
    def __init__(self, disponibilidade: dict[tuple[str, str], float],
                 quedas: list[tuple[str, float, float]], semente: int = 0,
                 janela_dias: float = 0.25):
        self.disponibilidade = {frozenset(k): v for k, v in disponibilidade.items()}
        self.quedas = quedas
        self.semente = semente
        self.janela_dias = janela_dias
        self.normalizada = False

    def vizinhos(self, no: str) -> list[str]:
        return sorted(next(iter(par - {no})) for par in self.disponibilidade if no in par)

    def fora_do_ar(self, no: str, dia: float) -> bool:
        return not self.normalizada and any(n == no and ini <= dia < fim for n, ini, fim in self.quedas)

    def link_ativo(self, a: str, b: str, dia: float) -> bool:
        if self.normalizada:
            return True
        if self.fora_do_ar(a, dia) or self.fora_do_ar(b, dia):
            return False
        p = self.disponibilidade.get(frozenset((a, b)), 0.0)
        janela = int(dia / self.janela_dias)
        # Sorteio determinístico por (enlace, janela): os dois lados concordam.
        u = random.Random(f"{self.semente}|{min(a, b)}|{max(a, b)}|{janela}").random()
        return u < p

    def normalizar(self) -> None:
        """Fim do experimento: todos os enlaces voltam, para medir a convergência."""
        self.normalizada = True
