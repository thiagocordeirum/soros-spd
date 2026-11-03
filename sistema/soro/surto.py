"""Detecção de aumento anormal de casos por região (método C2 do EARS, CDC).

Compara os casos do dia com a média de 7 dias que termina 3 dias antes. O
intervalo de 2 dias entre a linha de base e o dia avaliado evita que o próprio
surto puxe a média para cima. Há alarme quando os casos do dia passam da média
em mais de ``k`` desvios-padrão (Hutwagner et al., 2003).

Como os casos podem chegar atrasados (o posto registra e só depois sincroniza),
o detector reavalia os últimos dias a cada rodada.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from statistics import mean, pstdev


def casos_por_dia(casos: list[dict]) -> Counter:
    return Counter(date.fromisoformat(c["data"]) for c in casos)


def c2(contagens: Counter, dia: date, k: float = 3.0, sigma_min: float = 1.0,
       guarda: int = 2, base: int = 7) -> dict:
    fim = dia - timedelta(days=guarda + 1)
    dias_base = [fim - timedelta(days=i) for i in range(base)]
    linha_base = [contagens.get(d, 0) for d in dias_base]
    media = mean(linha_base)
    limiar = media + k * max(pstdev(linha_base), sigma_min)
    observado = contagens.get(dia, 0)
    tem_historico = any(contagens.get(d, 0) for d in dias_base) or min(contagens, default=dia) <= dias_base[-1]
    return {"dia": dia.isoformat(), "observado": observado, "media": round(media, 2),
            "limiar": round(limiar, 2), "alarme": bool(tem_historico and observado > limiar)}


def serie(contagens: Counter, ate: date, dias: int = 14) -> list[dict]:
    """Casos por dia e limiar C2 dos últimos ``dias``, para o gráfico do painel."""
    return [c2(contagens, ate - timedelta(days=i)) for i in reversed(range(dias))]


def id_alerta(regiao: str, dia: date) -> str:
    """Id determinístico: polo e secretaria que detectam o mesmo surto geram o mesmo alerta."""
    ano, semana, _ = dia.isocalendar()
    return f"surto:{regiao}:{ano}-S{semana:02d}"
