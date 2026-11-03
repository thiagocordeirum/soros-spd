"""Rede distribuída de controle de soros antivenenos.

Cada unidade da rede (secretaria estadual, polo ou ponto de soro) roda como um
nó independente: um processo com servidor web, banco SQLite próprio e uma
thread que sincroniza os dados com as unidades vizinhas.
"""

__version__ = "0.3.0"
