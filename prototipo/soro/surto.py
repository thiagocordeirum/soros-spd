"""Detecção de aumento anormal de casos por região (método C2 do EARS/CDC).

O C2 compara a contagem do dia com uma linha de base móvel de 7 dias que
termina 3 dias antes (o intervalo de guarda evita que o próprio surto
contamine a linha de base). Há alarme quando a contagem excede a média da
linha de base em mais de ``k`` desvios-padrão (Hutwagner et al., 2003).

Num sistema com notificação store-and-forward, as contagens dos últimos dias
ainda estão incompletas: casos registrados offline chegam atrasados. Por isso
o detector reavalia uma janela de dias recentes a cada execução.
"""
from __future__ import annotations

from collections import Counter
from statistics import mean, pstdev


def contagens_diarias(casos, regiao: str) -> Counter:
    return Counter(int(c["dia"]) for c in casos if c["regiao"] == regiao)


def c2(contagens: Counter, dia: int, k: float = 3.0, sigma_min: float = 1.0,
       guarda: int = 2, base: int = 7, inicio_serie: int = 0) -> tuple[bool, int, float]:
    """Devolve (alarme, observado, limiar) para o ``dia``.

    Sem linha de base completa (início da série histórica), não há alarme.
    ``sigma_min`` evita limiares irrisórios em regiões com poucos casos.
    """
    fim = dia - guarda - 1
    if fim - base + 1 < inicio_serie:
        return False, contagens.get(dia, 0), float("inf")
    linha_base = [contagens.get(d, 0) for d in range(fim - base + 1, fim + 1)]
    mu = mean(linha_base)
    sigma = max(pstdev(linha_base), sigma_min)
    limiar = mu + k * sigma
    observado = contagens.get(dia, 0)
    return observado > limiar, observado, limiar
