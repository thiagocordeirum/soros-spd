# Protótipo — logística distribuída de soros antivenenos

Prova de conceito da proposta (Entrega 1, Sistemas Paralelos e Distribuídos).
Usa só a biblioteca padrão do Python (3.10+); não há nada para instalar.

```bash
python3 demo.py              # simulação de 30 dias, ~15 s
python3 demo.py --verbose    # mostra também cada caso atendido e cada remessa recebida
python3 demo.py --painel 10 18 25   # painel da central nesses dias
python3 -m unittest -v       # propriedades dos CRDTs, rotas e detector de surto
python3 bench_paralelo.py    # ganho da análise N-1 com vários processos
```

## O que a demonstração faz

Oito nós (central em Manaus, polos em Tabatinga e Tefé, cinco postos) sobem
cada um com seu servidor TCP em `127.0.0.1`. Cada nó tem uma **réplica
completa** do estado e trabalha sobre ela mesmo sem rede; de tempos em tempos
faz uma rodada de **anti-entropia push-pull** com um vizinho escolhido ao acaso,
se o enlace estiver ativo naquele momento.

| Funcionalidade | Onde | Ideia de SPD |
|---|---|---|
| Inventário por posto e lote (FEFO, validade) | `soro/crdt.py` | CRDT: PN-Counter por (posto, lote); converge sem coordenação |
| Remessas em trânsito e capacidade refrigerada | `soro/crdt.py`, `demo.py` | G-Sets de remessas e de confirmações: o que foi enviado e não confirmado conta como estoque do destino; remessa nunca passa do espaço livre |
| Idade da informação ("visto há 3 dias") | `soro/crdt.py`, `soro/no.py` | Registrador de máximo por nó (último contato), propagado pelo gossip |
| Notificação de caso offline | `soro/crdt.py`, `soro/no.py` | G-Set + gossip = store-and-forward sem perda nem duplicação |
| Alerta de surto **por região** | `soro/surto.py`, `soro/no.py` | Detecção C2 (EARS/CDC) no polo e na central; id determinístico funde detecções repetidas; só os nós da região exibem |
| Roteamento do paciente ao posto com soro | `soro/grafo.py` | Dijkstra sobre grafo multimodal (voadeira, barco, estrada, avião) |
| Criticidade N-1 dos postos | `soro/grafo.py`, `bench_paralelo.py` | Tarefas independentes em `ProcessPoolExecutor` |
| Conectividade intermitente | `soro/rede.py` | Enlaces com disponibilidade parcial e quedas longas programadas |

O cenário (`soro/cenario.py`) tem municípios reais do Amazonas, mas **tempos de
viagem, estoques, enlaces e taxas de acidente são ilustrativos**.

## O que observar na saída

- **Atalaia do Norte** fica sem comunicação do dia 12 ao 21, justamente durante o
  surto no Alto Solimões. O alerta só chega lá depois da reconexão, e suas
  notificações chegam à central com dias de atraso — mas chegam todas.
- No dia 18 a central imprime um **painel** com o que sabe de cada nó e há quanto
  tempo: Atalaia aparece com informação de vários dias atrás.
- Como a remessa enviada a Atalaia continua "em trânsito" até a confirmação
  chegar, o polo **não repete** a remessa enquanto ela está isolada. Ainda há
  decisões com **visão desatualizada** (paciente encaminhado a um posto que já
  ficou sem soro): é o problema que o projeto quer medir e reduzir.
- Ao final, todos os enlaces voltam e as oito réplicas chegam ao **mesmo resumo
  (hash)** em milissegundos.

`saida_exemplo.txt` tem uma execução completa. Como o gossip depende do
escalonamento real, execuções diferentes variam um pouco nos detalhes.

## Limitações conhecidas (próximas entregas)

- Envia o estado inteiro a cada rodada (~30 MB em 30 dias); trocar por delta-CRDTs.
- O CRDT garante convergência, não estoque ≥ 0: duas réplicas isoladas podem
  dispensar o mesmo frasco (detectado em `saldos_negativos`, não evitado).
- Todos os nós rodam num único processo; o próximo passo é um processo/contêiner
  por nó, com partições reais (`tc netem`) e persistência local (SQLite).
