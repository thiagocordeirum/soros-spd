# Logística distribuída de soros antivenenos

Sistema web para que a secretaria estadual, os polos e os pontos de soro enxerguem o
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

As telas da equipe pedem login. O `exemplo` cria contas de demonstração, todas com a senha
que está em `SENHA_EXEMPLO`, no arquivo `soro/exemplo.py`. Cada pessoa entra pelo endereço
da própria unidade:

| Login | Tipo | Entra em |
|---|---|---|
| `gestor` | Gestão estadual | http://127.0.0.1:8000 |
| `coord.tabatinga`, `coord.tefe` | Coordenação do polo | 8001, 8005 |
| `prof.<unidade>` (ex.: `prof.atalaia`) | Profissional de saúde | porta da unidade (Atalaia: 8003) |

Numa rede sem nenhuma conta, a tela de login da secretaria pede a criação da primeira conta
de gestão; as outras são cadastradas na tela Equipe.

Depois abra no navegador:

| Endereço | Unidade | Tela principal |
|---|---|---|
| http://127.0.0.1:8000 | FVS-RCP (secretaria estadual) | Painel estadual |
| http://127.0.0.1:8001 | Polo Tabatinga | Painel do polo |
| http://127.0.0.1:8003 | Atalaia do Norte (posto) | Estoque e atendimento |
| qualquer nó + `/usuario.html` | | Onde tem soro (cidadão) |
| qualquer nó + `/docs` | | documentação interativa da API (Swagger, gerada pelo FastAPI) |

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
com `python -m soro no tabatinga` e veja na tela "Rede" os dados se acertarem.

## Telas

| Tela | Quem usa | O que faz |
|---|---|---|
| Entrar (`login.html`) | equipe | login; na secretaria, criação da primeira conta |
| Início | toda a equipe | resumo do nó e alertas ativos |
| Estoque e atendimento (`posto.html`) | profissional do posto ou do polo | lotes com validade, registro de atendimento com baixa no lote que vence antes, confirmação de remessa, pedido de soro, entrada de lote |
| Painel do polo (`polo.html`) | responsável do polo | sugestão de reposição para cada posto, estoque dos postos contra o alvo, pedidos, remessas a caminho, gráficos de casos, uso e vencimento |
| Painel estadual (`estado.html`) | secretaria | estoque de cada unidade, uso por mês, gráfico de por quantos meses dura, idade do dado, soro perto de vencer com sugestão de remanejamento, postos críticos, gráficos de uso, atendimentos e vencimento |
| Equipe (`equipe.html`) | toda a equipe | troca de senha e saída; para gestão e coordenação, cadastro, desativação e lista das contas |
| Seu perfil (`perfil.html`) | cidadão, opcional | nome, alergias, se já tomou soro, doenças e contato de emergência, guardados só no celular para mostrar à equipe |
| Onde tem soro (`usuario.html`) | cidadão, no celular, sem login | posto mais rápido de alcançar que tem o soro, com o caminho (barco, voadeira, estrada, avião) no mapa; a pessoa diz onde está pela lista, pelo GPS ou tocando no mapa; pode ser instalada na tela inicial |
| Rede (`rede.html`) | equipe técnica | vizinhos, última troca, vetor de versões e resumo dos dados |

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
gravado ao subir, então continuam funcionando sem internet. Se o arquivo não existir, as
telas mostram só o nome da unidade.

A rota é calculada pelo próprio sistema, com o algoritmo de Dijkstra sobre o mapa
de localidades e trechos do arquivo da rede. APIs comerciais de rota (Google Maps,
OpenRouteService e outras) só conhecem estradas e não sabem que na Amazônia o caminho é
pelo rio, além de exigirem internet.

O botão "Usar minha localização" usa a geolocalização do próprio navegador, que não é um
serviço externo. A página manda só a latitude e a longitude, e o servidor acha a localidade
do mapa mais perto. Tocar no mapa faz a mesma coisa. O navegador só libera a localização
em `localhost` ou em HTTPS; pelo IP da rede local, use a lista ou o toque no mapa.

## No celular

A tela do cidadão é um aplicativo web instalável. Abra `usuario.html` no navegador do
celular e use "Adicionar à tela inicial". Ela abre como aplicativo e, sem conexão, mostra a
última busca feita. Para instalar e usar o GPS, o celular precisa acessar o nó por HTTPS
(por exemplo, por um túnel como o `cloudflared tunnel --url http://127.0.0.1:8000`).

O desenho do mapa usa Leaflet com o fundo do OpenStreetMap, que são gratuitos e não pedem
chave nem cadastro. É a única coisa que vem de fora: o navegador baixa a biblioteca e as
imagens do mapa pela internet. A rota continua sendo calculada pelo sistema. Sem internet,
a tela mostra no lugar um mapa esquemático desenhado a partir das coordenadas cadastradas,
e a busca funciona do mesmo jeito.

Cada resultado da tela do cidadão tem o botão "Abrir no Google Maps", que é só um link
(`google.com/maps/dir/?api=1&destination=lat,lon`) com as coordenadas do CNES. Não precisa
de chave nem de conta. Serve para o último trecho, dentro da cidade, porque o Google Maps
só traça caminho por estrada. Colocar o mapa do Google dentro da página exigiria chave da
API do Google com cobrança ativada; por isso o mapa da tela continua com Leaflet e
OpenStreetMap.

No mapa, cada trecho aparece como uma linha reta entre duas localidades. O tempo de viagem
é o do cadastro, mas o desenho não acompanha a curva do rio.

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
soro/servidor.py        servidor HTTP em FastAPI: API, páginas e sincronização
soro/surto.py           detecção de surto (método C2)
soro/cnes.py            importação dos estabelecimentos pela API do CNES
soro/rotas.py           rotas e postos críticos em paralelo
soro/exemplo.py         dados de exemplo
soro/avaliacao.py       medição das quatro perguntas
soro/web/               páginas (HTML, CSS e JavaScript; só a tela do cidadão usa Leaflet)
                        manifest.webmanifest e sw.js tornam a tela do cidadão instalável
tests/                  testes automatizados
docs/especificacao.md   especificação de projeto
```

A especificação completa (requisitos, arquitetura, protocolo de sincronização, API e
avaliação) está em [docs/especificacao.md](docs/especificacao.md).

## Usar em outro estado

Copie `redes/amazonas.json`, troque as unidades, os vizinhos, as capacidades, os
estoques-alvo e o mapa, e rode `python -m soro rede --config redes/<estado>.json`. O
código não muda.
