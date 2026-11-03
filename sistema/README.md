# Logística distribuída de soros antivenenos

Sistema com API HTTP para que a secretaria estadual, os polos e os pontos de soro enxerguem o
mesmo estoque, registrem atendimentos e recebam alertas de surto, sem depender de um
servidor central. Projeto da disciplina Sistemas Paralelos e Distribuídos (UEA/EST, 2026).

Grupo: Cristiano Peniche Ceccon, João Victor Mattos Lopes e Thiago Cordeiro de Melo.

## Como rodar

Precisa de Python 3.10 ou mais novo. O servidor de cada nó usa FastAPI com uvicorn; instale
uma vez num ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Com o ambiente ativado:

```bash
python -m soro rede         # sobe os 8 nós do exemplo do Amazonas, um processo por nó
python -m soro exemplo      # em outro terminal: carrega dados de exemplo e cria as contas
```

As operações da equipe exigem autenticação no nó da própria unidade. O comando
`exemplo` cria contas de demonstração com a senha definida em `SENHA_EXEMPLO`,
no arquivo `soro/exemplo.py`.

| Login | Tipo | Porta do nó |
|---|---|---|
| `gestor` | Gestão estadual | 8000 |
| `coord.tabatinga`, `coord.tefe` | Coordenação do polo | 8001, 8005 |
| `prof.<unidade>` (ex.: `prof.atalaia`) | Profissional de saúde | porta da unidade (Atalaia: 8003) |

Numa rede sem contas, crie a primeira conta de gestão por `POST /api/usuarios` no nó
da secretaria. Autentique-se com `POST /api/entrar` e mantenha o cookie de sessão nas
requisições seguintes. `soro/cliente.py` fornece um cliente HTTP com esse suporte.

Cada nó oferece a documentação interativa da API em `/docs` e o esquema em
`/openapi.json`. Exemplo: http://127.0.0.1:8000/docs.

As portas 8000 a 8007 estão em `redes/amazonas.json`. Ctrl+C no primeiro terminal para
todos os nós. Os dados ficam em `dados/<unidade>.db` e continuam lá quando a rede sobe
de novo; para começar do zero, apague a pasta `dados`.

Outros comandos:

```bash
python -m soro no atalaia              # sobe um nó só (por exemplo, em outro computador)
python -m soro avaliar                 # mede as quatro perguntas da avaliação
python -m soro speedup                 # mede só o ganho do paralelismo
python3 -m unittest -v                  # testes automatizados
```

Para testar a falha de um nó com a rede no ar, encerre o processo de um polo
(`kill <pid>`) e continue registrando atendimentos nos postos. Depois suba o polo de novo
com `python -m soro no tabatinga` e consulte `/api/sincronizacao` para acompanhar a convergência dos dados.

## API

Os endpoints cobrem estoque por lote, atendimentos, pedidos, remessas, alertas,
indicadores, contas e sincronização. A consulta pública de soro fica em
`GET /api/onde-tem-soro`, sem necessidade de conta. Informe `local` ou `lat` e `lon`,
e opcionalmente `agravo`; a resposta traz destinos ordenados pelo tempo de viagem,
o trajeto, o estoque e a idade da informação.

## O sistema usa alguma API externa?

Só para importar dados, nunca com a rede rodando. O comando abaixo consulta a API de Dados
Abertos do Ministério da Saúde (CNES, pública e sem chave) e baixa o nome, o endereço, o
telefone e as coordenadas do estabelecimento de cada unidade:

```bash
python -m soro cnes        # grava redes/amazonas.cnes.json
```

O código CNES de cada unidade fica no arquivo da rede. Os do exemplo vêm da lista oficial
de pontos estratégicos de soro do Amazonas (Hospital de Guarnição de Tabatinga, Hospital
Geral de Benjamin Constant, Hospital Regional de Tefé e outros). Os nós leem o arquivo
gravado ao subir, então continuam funcionando sem internet. Se o arquivo não existir, a
API informa só o nome da unidade.

A rota é calculada pelo próprio sistema, com o algoritmo de Dijkstra sobre o mapa
de localidades e trechos do arquivo da rede. APIs comerciais de rota (Google Maps,
OpenRouteService e outras) só conhecem estradas e não sabem que na Amazônia o caminho é
pelo rio, além de exigirem internet.

A busca aceita coordenadas e encontra a localidade cadastrada mais próxima,
informando a distância até ela. O grafo guarda os tempos e meios de transporte dos
trechos, sem a geometria do percurso dos rios.

## Estrutura

```
redes/amazonas.json     rede de exemplo: unidades, vizinhos, capacidades, códigos CNES, mapa
redes/amazonas.cnes.json  dados dos estabelecimentos baixados do CNES
soro/config.py          leitura e validação do arquivo da rede
soro/diario.py          diário de eventos em SQLite, vetor de versões
soro/no.py              regras de negócio de uma unidade
soro/usuarios.py        tipos de conta, permissões e senha (PBKDF2)
soro/cliente.py         cliente HTTP com login, usado pelo exemplo, pela avaliação e pelos testes
soro/sincronizacao.py   troca de dados entre vizinhos (gossip)
soro/servidor.py        servidor HTTP em FastAPI: API e sincronização
soro/surto.py           detecção de surto (método C2)
soro/cnes.py            importação dos estabelecimentos pela API do CNES
soro/rotas.py           rotas e postos críticos em paralelo
soro/exemplo.py         dados de exemplo
soro/avaliacao.py       medição das quatro perguntas
tests/                  testes automatizados
docs/especificacao.md   especificação de projeto
```

A especificação completa (requisitos, arquitetura, protocolo de sincronização, API e
avaliação) está em [docs/especificacao.md](docs/especificacao.md).

## Usar em outro estado

Copie `redes/amazonas.json`, troque as unidades, os vizinhos, as capacidades, os
estoques-alvo e o mapa, e rode `python -m soro rede --config redes/<estado>.json`. O
código não muda.
