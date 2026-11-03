# Logística distribuída de soros antivenenos

Projeto da disciplina Sistemas Paralelos e Distribuídos (UEA/EST, 2026/2), professor
Ricardo Rios. Grupo: Cristiano Peniche Ceccon, João Victor Mattos Lopes e Thiago Cordeiro
de Melo.

Sistema para que a secretaria estadual, os polos e os pontos de soro do Amazonas enxerguem
o mesmo estoque de soro antiveneno, registrem atendimentos e recebam alertas de surto por
região, sem depender de um servidor central nem de internet contínua. O cidadão vê onde
há soro e o caminho mais rápido até lá, inclusive por rio.

| Pasta | Conteúdo |
|---|---|
| [sistema/](sistema/) | o sistema: um nó por unidade (FastAPI + SQLite), sincronização por gossip, telas web, testes e avaliação. Comece pelo [README](sistema/README.md) |
| [sistema/docs/especificacao.md](sistema/docs/especificacao.md) | especificação de projeto |
| [relatorio-v1/](relatorio-v1/) | relatório (LaTeX e PDF) |
| [entrega1/](entrega1/) | proposta |
| `Soros-slides.pdf` | slides |
| [prototipo/](prototipo/), [prototipos/](prototipos/) | primeiro protótipo da simulação e protótipo das telas |
| [requisitos/](requisitos/) | levantamento de requisitos |
