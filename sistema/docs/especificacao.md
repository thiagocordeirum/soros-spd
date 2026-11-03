# Especificação de projeto

Sistema distribuído para logística de soros antivenenos dentro de um estado. Este documento
descreve os requisitos atendidos, a arquitetura, o modelo de dados, o protocolo de
sincronização, a parte paralela, a API HTTP e a avaliação. O código está em `soro/`.

## 1. Escopo

O Ministério da Saúde compra o soro e manda uma cota mensal para cada estado. O sistema
começa nesse ponto: a cota é a entrada de estoque da secretaria estadual. Dali para baixo,
a secretaria abastece polos regionais, e os polos abastecem hospitais, postos e polos base
indígenas. Hoje essa parte é feita por planilha, e-mail, telefone, rádio e WhatsApp, e
nenhum sistema mostra quantas ampolas cada ponto tem.

O sistema não substitui os sistemas oficiais (SIES, Sinan, SI-PNI). Ele liga os níveis da
rede estadual e pode, no futuro, exportar dados para esses sistemas.

O exemplo usado em todo o projeto é o Amazonas: FVS-RCP em Manaus, polos em Tabatinga e
Tefé, e cinco pontos de soro. Coordenadas são aproximadas; tempos de viagem, estoques e
comunidades são ilustrativos.

## 2. Requisitos

### 2.1 Funcionais

| Id | Requisito | Onde está |
|---|---|---|
| RF01 | Cada unidade registra e consulta seus dados mesmo que as outras estejam fora do ar | `no.py`, `servidor.py` |
| RF02 | A unidade sincroniza sozinha com as vizinhas e também quando o usuário pede | `sincronizacao.py`, tela Rede |
| RF03 | Toda informação de outra unidade mostra há quanto tempo foi atualizada | `diario.py` (contatos), todas as telas |
| RF04 | A rede de qualquer estado é descrita num arquivo: níveis, quem abastece quem, vizinhos, capacidade da geladeira, estoque-alvo, código CNES e mapa; nome, endereço, telefone e coordenadas vêm do CNES | `config.py`, `cnes.py`, `redes/*.json` |
| RF05 | Estoque por lote com validade; a saída usa o lote que vence antes; lote vencido não sai | `No.lotes`, `No._baixar` |
| RF06 | Soro perto de vencer gera aviso com sugestão de para onde remanejar | `No.vencimentos`, painel estadual |
| RF07 | O posto pede soro ao seu fornecedor | `No.pedir`, tela do posto |
| RF08 | Remessa entre unidades: o que está a caminho conta como estoque do destino, a remessa não passa do espaço livre do destino e o destino confirma o recebimento, informando divergência | `No.enviar_remessa`, `No.receber_remessa` |
| RF09 | O fornecedor recebe uma sugestão de quanto mandar para cada unidade que abastece | `No.sugestoes`, painel do polo |
| RF10 | Registro de atendimento sem dados pessoais, com baixa automática do soro; reenviar o mesmo atendimento não duplica | `No.atender` |
| RF11 | Polo e secretaria detectam aumento anormal de casos por região e emitem alerta para a região | `surto.py`, `No.vigiar` |
| RF12 | Painel estadual com estoque, uso por mês, duração do estoque e idade do dado de cada unidade | `No.painel`, `estado.html` |
| RF13 | O cidadão vê o caminho até o lugar mais rápido de alcançar que tem o soro, informando onde está pela lista, pela posição do celular ou tocando no mapa; a tela funciona no celular e pode ser instalada | `rotas.py`, `usuario.html`, `sw.js` |
| RF14 | Cálculo de postos críticos em paralelo | `rotas.postos_criticos` |
| RF15 | Gráficos de uso diário, atendimentos por tipo de acidente, vencimento por mês, duração do estoque e estoque contra o alvo | `No.graficos`, `app.js` |
| RF16 | Contas da equipe em três tipos (profissional de saúde, coordenação do polo, gestão estadual), cada um com suas permissões; login no nó da própria unidade, sem consultar outro nó; cada registro guarda quem o fez | `usuarios.py`, `No.cadastrar`, `No.autenticar`, `servidor.py` |
| RF17 | O cidadão não tem conta; pode guardar no próprio celular um perfil opcional para mostrar à equipe | `perfil.html` |

Ficam para depois: cadastro de unidades por tela, login e permissões, relatórios,
exportação para os sistemas oficiais e desenho dos trechos seguindo o curso dos rios.

### 2.2 Não funcionais

| Id | Requisito | Como é atendido |
|---|---|---|
| RNF01 | Disponibilidade: nenhuma operação de usuário espera outro nó | toda gravação é local; a sincronização roda em outra thread |
| RNF02 | Convergência: nós que receberam os mesmos registros têm o mesmo estado | diário de eventos imutáveis + junção por união (seção 5) |
| RNF03 | Nenhum registro perdido ou duplicado | vetor de versões, prefixo contínuo e id gerado no navegador |
| RNF04 | Durabilidade: o que a tela confirmou está gravado em disco | SQLite em modo WAL, gravação antes da resposta |
| RNF05 | Várias pessoas usando o mesmo nó ao mesmo tempo sem estoque negativo | servidor com uma thread por requisição + trava no nó + um único escritor por estoque |
| RNF06 | Funciona numa rede local sem internet | FastAPI e uvicorn instalados uma vez (`requirements.txt`); as telas da equipe não usam recursos externos; a do cidadão cai para o mapa esquemático sem internet |
| RNF07 | A correção não depende de relógios sincronizados | a junção não usa horário; o relógio só aparece em estatísticas e na idade do dado |
| RNF08 | O cálculo pesado ganha velocidade com mais processadores | `ProcessPoolExecutor` (seção 9) |
| RNF09 | Privacidade: nenhum dado que identifique o paciente | o atendimento guarda só data, animal, gravidade, soro, ampolas e local |
| RNF10 | O mesmo código serve para qualquer estado | toda a rede vem do arquivo de configuração |
| RNF11 | Segurança das contas: a senha não é guardada nem trafega entre nós | só sal e hash PBKDF2-SHA256 (200 mil iterações); sessão em cookie HttpOnly e SameSite=Strict, um por nó; login errado demora 0,4 s |

### 2.3 Regras de negócio

| Id | Regra |
|---|---|
| RN01 | Sai primeiro o lote que vence antes |
| RN02 | Lote vencido não pode ser usado |
| RN03 | O antibotrópico-laquético pode substituir o antibotrópico (acidente com jararaca) |
| RN04 | Entrada, remessa e recebimento não podem passar do espaço livre da geladeira |
| RN05 | Remessa enviada e ainda não confirmada conta como estoque do destino |
| RN06 | Com alerta de surto ativo na região, o estoque-alvo das unidades dela dobra |
| RN07 | Um alerta vale por 7 dias; enquanto vale, a região não recebe outro |
| RN08 | A busca do cidadão só mostra lugares com pelo menos 4 ampolas do soro (configurável) |
| RN09 | Destinos a mais de 6 horas aparecem marcados (configurável) |
| RN10 | O sistema não sugere dose nem conduta; quem aplica informa as ampolas |
| RN11 | Só a secretaria cria a primeira conta, de gestão, e só enquanto a rede não tem nenhuma |
| RN12 | A gestão cadastra qualquer conta; a coordenação cadastra só profissionais do seu polo e dos postos que ele abastece |
| RN13 | Gestão estadual só existe na secretaria, coordenação só em polo, profissional em polo ou posto |

## 3. Arquitetura

### 3.1 Um nó por unidade

Cada unidade da rede (secretaria, polo ou ponto de soro) é um nó: um processo próprio,
que pode rodar num computador do próprio local. O nó tem quatro partes:

```
            navegador (profissional, gestor ou cidadão)
                         |  HTTP
   +---------------------v----------------------+
   | FastAPI + uvicorn (rotas rodam em threads)  |
   |    API JSON  |  páginas  |  /sync           |
   +------+--------------------------+----------+
          |                          |
   +------v---------+        +-------v---------+      outros nós
   | regras do nó   |        | sincronizador   |<---->  (vizinhos)
   | (no.py) +trava |        | thread de gossip|   HTTP
   +------+---------+        +-------+---------+
          |                          |
   +------v--------------------------v---------+
   |  diário de eventos (SQLite, modo WAL)      |
   +--------------------------------------------+
```

Uma thread de vigilância roda nos polos e na secretaria e verifica surtos a cada 10 s.

### 3.2 Topologia do exemplo

```
                     FVS-RCP (estado, :8000)
                    /                        \
     Polo Tabatinga (:8001) ------------ Polo Tefé (:8005)
     /        |          \                 /         \
Benjamin   Atalaia    Umariaçu         Alvarães --- Uarini
 (:8002) -- (:8003)   (:8004)          (:8006)     (:8007)
```

As linhas são os pares que sincronizam diretamente. A hierarquia (quem abastece quem)
segue a distribuição real; a vizinhança de sincronização pode ter atalhos, como
Benjamin Constant e Atalaia do Norte, que trocam dados entre si. Assim, se o polo cair,
os dois postos continuam se vendo.

### 3.3 Por que não um servidor central

Os dados nascem em muitos lugares e mudam ao mesmo tempo, e o registro no posto não pode
parar se o servidor da secretaria cair, faltar energia no polo ou a conexão via satélite
falhar. Pelo teorema CAP, durante uma partição é preciso escolher entre recusar
operações (consistência) ou aceitá-las e acertar depois (disponibilidade). O projeto
escolhe disponibilidade com convergência garantida.

Alternativas descartadas:

* Banco central: um ponto único de falha. A próxima etapa da avaliação vai comparar com
  esse modelo e contar quantos registros ele recusaria em cada queda.
* Consenso (Raft, Paxos): exige maioria de nós conectados para gravar; um posto isolado
  não conseguiria registrar nada.
* Blockchain: também depende de consenso, e os participantes são todos do SUS, sem
  desconfiança mútua a resolver.

## 4. Modelo de dados

Tudo é um evento imutável no diário (`diario.py`). Cada evento tem:

| Campo | Significado |
|---|---|
| `origem` | unidade que criou o evento |
| `seq` | número de sequência dentro da origem: 1, 2, 3... |
| `tipo` | `mov`, `caso`, `remessa`, `receb`, `pedido`, `alerta`, `usuario` ou `usuario_alt` |
| `chave` | identificador de domínio (id do caso, da remessa, do alerta ou `unidade/lote`) |
| `dados` | conteúdo em JSON |
| `quando` | horário de criação, só para exibição |

Tipos de evento:

| Tipo | Quem cria | Dados |
|---|---|---|
| `mov` | a unidade dona do estoque | unidade, soro, lote, validade, qtd (positiva entra, negativa sai), motivo (entrada, dispensa, envio, recebimento, perda), ref, data |
| `caso` | o ponto que atendeu | id, unidade, região, data, agravo, gravidade, soro, ampolas, local, atendido, encaminhado_para |
| `remessa` | quem envia | id, origem, destino, soro, itens (lote, validade, qtd), qtd, pedido |
| `receb` | quem recebe | remessa, destino, qtd, divergência |
| `pedido` | quem pede | id, unidade, para, soro, qtd |
| `alerta` | polo ou secretaria | id, região, dia, observado, média, limiar, por |
| `usuario` | quem cadastra | login, nome, tipo, unidade, sal, hash, iter, criado_por, data |
| `usuario_alt` | quem desativa, reativa ou troca a senha | id, login, em (hora), ativo ou sal, hash, iter |

`mov`, `caso`, `remessa`, `receb` e `pedido` levam também `por`, o login de quem fez.

O estado que as telas mostram é calculado a partir dos eventos:

* saldo de um lote numa unidade = soma de `qtd` dos `mov` daquela unidade e lote;
* em trânsito = remessas sem `receb` correspondente;
* uso por mês = soma das saídas por dispensa nos últimos 90 dias, vezes 30/90;
* casos, pedidos e alertas = conjunto de eventos daquele tipo, sem repetição de `chave`;
* contas = o primeiro `usuario` de cada login na ordem do diário, com os `usuario_alt`
  aplicados em ordem de `em` (e de `id` no empate). Todos os nós ordenam do mesmo jeito,
  então chegam à mesma situação; com relógios desacertados, duas mudanças quase
  simultâneas na mesma conta podem ficar na ordem errada, o que só afeta qual delas vale.

Somas e uniões não dependem da ordem em que os eventos chegam. Esse é o ponto que garante
que todos os nós calculam o mesmo estado quando têm os mesmos eventos.

O nó guarda também uma tabela `contato` (unidade, instante mais recente conhecido). Ela é
um registrador de máximo: na junção fica o maior valor. É daí que sai a idade da
informação mostrada nas telas.

## 5. Sincronização

### 5.1 Vetor de versões e prefixo contínuo

O vetor de versões de um nó é `{origem: maior seq que ele tem}`. Um nó só aceita o evento
`seq = n` de uma origem se já tiver o `n - 1`. Com isso, para cada origem ele sempre guarda
um prefixo contínuo 1..n, e o vetor descreve exatamente o conjunto de eventos que ele tem.
Comparar dois vetores diz o que falta a cada lado sem listar evento por evento.

A gravação dos eventos recebidos é feita numa única transação. Se o processo cair no meio,
nada fica pela metade e o prefixo continua contínuo.

### 5.2 Protocolo

A cada 2 s (com variação aleatória de 40% para os nós não sincronizarem todos juntos),
cada nó escolhe um vizinho ao acaso e faz uma troca em duas etapas:

```
nó A                                             vizinho B
  | POST /sync {de, vetor_A, contatos_A}            |
  |------------------------------------------------>|
  |      {eventos que A não tem, vetor_B, contatos_B}|
  |<------------------------------------------------|
  | grava os eventos (uma transação)                |
  | POST /sync/eventos {eventos que B não tem}      |
  |------------------------------------------------>|
  |                         {novos}                 |
  |<------------------------------------------------|
```

Se o vizinho não responde em 5 s, a troca é abandonada e o nó tenta outro vizinho na
rodada seguinte. Como cada evento fica guardado até alguém confirmar que tem, o que foi
registrado num nó isolado chega aos outros quando qualquer caminho se abrir: é um esquema
de armazenar e encaminhar (store-and-forward) pela vizinhança.

### 5.3 Por que converge

1. Eventos nunca mudam depois de criados.
2. Juntar dois diários é fazer a união dos conjuntos de eventos, operação comutativa,
   associativa e idempotente. O diário é, portanto, um CRDT do tipo conjunto que só
   cresce (G-Set).
3. O estado derivado usa somas e uniões, que não dependem da ordem.
4. A troca anti-entropia entre vizinhos, repetida, leva todo evento a todos os nós
   conectados (algoritmo epidêmico, Demers et al., 1987).

Logo, quando a rede fica estável, todos os nós chegam ao mesmo conjunto de eventos e ao
mesmo estado. O `resumo` (hash do conjunto) permite verificar isso.

### 5.4 Um único escritor por estoque

O saldo de uma unidade só muda por eventos criados por ela mesma: quem envia grava a saída,
quem recebe grava a entrada. Dentro do nó, as operações que leem o saldo e depois gravam
passam por uma trava. Com isso não existe o caso de dois nós darem saída no mesmo frasco,
e o saldo nunca fica negativo.

## 6. Concorrência dentro do nó

O servidor é uma aplicação FastAPI servida pelo uvicorn. As rotas são funções comuns
(`def`, não `async`), e o FastAPI roda cada uma numa thread do seu pool; assim várias
requisições são atendidas ao mesmo tempo sem que as regras do nó precisem ser assíncronas.
Os pontos compartilhados são o diário (protegido por uma trava interna e pelo SQLite) e as regras do
nó (trava `No._trava` em atendimento, remessa, recebimento, entrada e perda). A
sincronização e a vigilância são threads separadas que usam as mesmas travas.

O atendimento recebe um `id` gerado no navegador. Se a mesma requisição chegar duas vezes,
por exemplo quando a rede local falha e o navegador tenta de novo, o nó devolve o caso já
gravado e não dá baixa de novo no soro.

## 7. Funções

### 7.1 Atendimento

1. O profissional informa animal, gravidade e ampolas aplicadas.
2. O nó procura, entre os soros aceitos para o animal (RN03), o primeiro com saldo
   suficiente, ignorando lotes vencidos.
3. Dá baixa lote a lote, do que vence antes ao que vence depois.
4. Se nenhum soro tem saldo, o caso é gravado como não atendido e a tela mostra os três
   lugares mais rápidos de alcançar com soro, segundo a última informação de cada um.

### 7.2 Reposição

Para cada unidade abastecida e cada soro do estoque-alvo dela:

```
alvo      = estoque-alvo (dobrado se houver alerta na região)
tem       = saldo do destino, segundo a última informação
a_caminho = remessas para o destino ainda não confirmadas
cabe      = capacidade - estoque total do destino - tudo a caminho dele
se tem + a_caminho >= 50% do alvo: não sugere
se há remessa a caminho: aguarda
senão: sugere min(alvo - tem - a_caminho, cabe, saldo do fornecedor)
```

A regra de contar o que está a caminho veio do protótipo anterior: sem ela, o polo
continuava mandando soro para um posto isolado, porque não via o recebimento.

### 7.3 Vencimento e remanejamento

Lotes com validade nos próximos 60 dias aparecem no painel. A sugestão é mandar para a
unidade (fora a secretaria) onde o estoque daquele soro dura menos meses, considerando o
uso por mês, desde que haja espaço livre.

### 7.4 Detecção de surto

Método C2 do EARS (CDC): para o dia avaliado, a linha de base é a média e o desvio-padrão
dos casos nos 7 dias que terminam 3 dias antes. Há alarme quando os casos do dia passam de
`média + 3 x max(desvio, 1)`. Sem histórico anterior à linha de base não há alarme.

Como casos de postos isolados chegam atrasados, cada rodada reavalia hoje e os dois dias
anteriores. O id do alerta é `surto:<região>:<ano>-S<semana>`: se o polo e a secretaria
detectarem o mesmo surto, os dois geram o mesmo id e o alerta aparece uma vez só.

### 7.5 Onde tem soro (cidadão)

O mapa é um grafo: localidades com coordenadas e trechos com tempo e meio de transporte.
A rota é calculada com o algoritmo de Dijkstra a partir da localidade do usuário. Há três
jeitos de dizer onde a pessoa está: escolher na lista, usar a posição do celular ou tocar no
mapa. Nos dois últimos a página manda só a latitude e a longitude
(`/api/onde-tem-soro?lat=&lon=`), e o servidor escolhe a localidade do mapa mais perto em
linha reta e devolve essa distância. Se passar de 2 km, a tela avisa de qual ponto a busca
partiu. O resultado lista os
lugares com soro, do mais rápido ao mais lento, com o caminho passo a passo, o estoque e a
idade da informação.

Não há API externa de rota. As APIs comerciais de rota só conhecem estradas e não
calculam trajetos por rio. A geolocalização é do próprio navegador.

Cada unidade pode ter o código CNES do estabelecimento que guarda o soro. O comando
`python -m soro cnes` (`cnes.py`) consulta a API de Dados Abertos do Ministério da Saúde
(`apidadosabertos.saude.gov.br/cnes/estabelecimentos/{codigo}`), que é pública e sem chave, e
grava nome, endereço, telefone e coordenadas em `redes/<rede>.cnes.json`. O carregamento da
configuração junta esses dados às unidades. A API só é chamada nessa importação; com a rede
rodando, nenhum nó depende dela. Os códigos do exemplo vêm da lista oficial de pontos
estratégicos de soro do Amazonas; o do Polo Base Umariaçu foi achado pela busca de
estabelecimentos de Tabatinga e não está naquela lista.

O resultado da busca mostra o estabelecimento, o endereço, um link de ligação para o
telefone e o link "Abrir no Google Maps" com as coordenadas do CNES. O link não precisa de
chave; o mapa do Google embutido na página precisaria de chave com cobrança, e por isso não
foi usado.

O mapa da tela usa Leaflet 1.9.4 (cdnjs) com o fundo do OpenStreetMap, ambos gratuitos e
sem chave. Por cima do fundo aparecem as localidades, os pontos com soro, os trechos (linha
tracejada para avião) e o caminho escolhido em laranja. Tocar num resultado mostra o
caminho daquele destino. Quando a busca usa a posição do navegador, o mapa marca a pessoa e
a liga à localidade mais próxima. Se a biblioteca não carregar por falta de internet, a
página desenha um mapa esquemático em SVG com as mesmas informações. Os trechos são retas
entre localidades, porque o arquivo da rede guarda só o tempo de cada trecho e não o
percurso do rio.

A tela foi feita para celular. Tem botões grandes para ligar 192 e 193, escolha do animal
por botões, abas Lista e Mapa em telas estreitas e as orientações de primeiro socorro do
Ministério da Saúde. Ela é um aplicativo web instalável (PWA): `manifest.webmanifest`
permite "Adicionar à tela inicial" e `sw.js` guarda a página e as últimas respostas da API.
Sem conexão, a página abre e mostra a última busca com a data em que foi feita. Não há
aplicativo nativo; o mesmo código serve para computador e celular.

O navegador só libera a posição do celular e o service worker em HTTPS ou em `localhost`.
Acessando o nó pelo IP da rede local, a busca pela lista e pelo toque no mapa funcionam,
mas o botão de localização não.

### 7.6 Gráficos

Os painéis buscam `/api/graficos`, que resume os eventos das unidades que o nó acompanha:
ampolas usadas por dia por soro (30 dias), atendimentos por região e tipo de acidente
(30 dias) e ampolas que vencem por mês por soro (18 meses). O painel estadual também mostra
por quantos meses o estoque de cada unidade dura, com a referência de 2 meses, e o do polo
mostra o estoque de cada posto ao lado do estoque-alvo. Cada soro tem uma cor fixa, e cada
tipo de acidente usa a cor do seu soro principal. As quatro cores foram conferidas para
daltonismo nos temas claro e escuro. Todo gráfico tem uma tabela com os mesmos números
("Ver os números") e mostra o valor ao passar o mouse ou focar com o teclado.

### 7.7 Contas e permissões

A pessoa entra pelo nó da sua unidade. O nó confere a senha com o hash que recebeu pela
sincronização e abre uma sessão na memória (12 horas), entregue num cookie com o nome do
nó, porque todos os nós de teste rodam em 127.0.0.1 e o navegador não separa cookies por
porta. As rotas da equipe exigem sessão e, para mudar algo, a permissão do tipo da conta:

| Ação | Profissional | Coordenação | Gestão |
|---|---|---|---|
| ver estoque, casos, remessas, alertas, gráficos | sim | sim | sim |
| registrar atendimento, entrada, perda, recebimento, pedido | sim | sim | sim |
| enviar remessa | | sim | sim |
| painel, sugestões de reposição, postos críticos | | sim | sim |
| cadastrar e desativar contas | | da sua região | todas |

Ficam abertas a troca entre nós (`/sync`), `/api/info`, os contadores da sincronização e
as rotas da tela do cidadão. Sem sessão a resposta é 401 e a tela leva ao login; sem
permissão, 403. A conta criada na secretaria só vale num posto depois de chegar a ele pela
sincronização, o que leva alguns segundos; desativar uma conta também se espalha assim.

O cidadão não tem conta. O perfil opcional dele (`perfil.html`) fica no `localStorage` do
celular e nunca é enviado a um nó.

## 8. Persistência

Um arquivo SQLite por nó (`dados/<unidade>.db`), em modo WAL:

```sql
CREATE TABLE eventos (origem TEXT, seq INTEGER, tipo TEXT, chave TEXT,
                      dados TEXT, quando REAL, PRIMARY KEY (origem, seq));
CREATE TABLE contato (unidade TEXT PRIMARY KEY, quando REAL);
```

O nó recalcula o estado a partir dos eventos quando chega evento novo e guarda o resultado
em memória até a próxima mudança.

## 9. Parte paralela: postos críticos

Pergunta: se o posto P ficar sem soro, quantas comunidades hoje a até 6 horas de algum
soro passam a ficar a mais de 6 horas?

1. Calcula a cobertura atual com um Dijkstra de múltiplas origens (todas as unidades com
   o soro).
2. Para cada unidade P, roda outro Dijkstra de múltiplas origens sem P e conta as
   comunidades descobertas.

As simulações do passo 2 são independentes. Elas são divididas em blocos e distribuídas
num `ProcessPoolExecutor`. O grafo vai uma vez para cada processo (via `initializer`), e
cada tarefa leva só a lista de unidades a remover. Usamos processos, e não threads, porque
o interpretador Python executa uma thread de cada vez em código puro (GIL).

## 10. API HTTP

Cada nó publica a documentação interativa em `/docs` (Swagger) e o esquema em
`/openapi.json`, gerados pelo FastAPI a partir das rotas e dos modelos Pydantic de
`servidor.py`. Corpo inválido devolve 422, regra de negócio violada devolve 409 e o que
não existe devolve 404, sempre no formato `{"erro": "..."}`.

Todas as respostas são JSON. Erros de regra de negócio voltam com status 409 e
`{"erro": "mensagem"}`.

| Método | Caminho | Uso |
|---|---|---|
| GET | `/api/info` | dados do nó e da rede |
| GET | `/api/estoque?unidade=` | lotes, total, capacidade, espaço livre, remessas a caminho |
| POST | `/api/entradas` | `{soro, lote, validade, qtd}` entrada de lote |
| POST | `/api/perdas` | `{lote, qtd, motivo}` perda ou descarte |
| POST | `/api/casos` | `{id, agravo, gravidade, ampolas, data}` atendimento |
| GET | `/api/casos?regiao=&unidade=` | últimos atendimentos |
| GET | `/api/remessas` | remessas chegando, enviadas e pedidos |
| POST | `/api/remessas` | `{destino, soro, qtd, pedido}` envia remessa |
| POST | `/api/remessas/<id>/receber` | `{qtd}` confirma recebimento |
| POST | `/api/pedidos` | `{soro, qtd}` pede soro ao fornecedor |
| GET | `/api/sugestoes` | sugestão de reposição |
| GET | `/api/alertas?recalcular=1` | alertas ativos |
| GET | `/api/vigilancia` | casos por dia e limite C2 por região |
| GET | `/api/painel` | painel do polo ou do estado |
| GET | `/api/criticos?soro=&processos=` | postos críticos |
| GET | `/api/localidades` | mapa (localidades e trechos) |
| GET | `/api/onde-tem-soro?local=` ou `?lat=&lon=` e `&agravo=` | rota até o soro (com `distancia_km` quando vem coordenada) |
| GET | `/api/graficos?dias=&unidade=` | séries dos gráficos |
| GET | `/api/sincronizacao` | vetor, total, resumo, vizinhos |
| GET | `/api/contagem` | número de eventos, casos, remessas, pedidos e alertas |
| POST | `/api/sincronizar` | força uma troca com cada vizinho |
| POST | `/sync`, `/sync/eventos` | usados entre nós |

## 11. Configuração de um estado

`redes/amazonas.json` tem:

* `soros` e `agravos` (cada animal com a lista de soros aceitos, em ordem de preferência);
* `parametros` (intervalos, dias de aviso de vencimento, limite de horas, ampolas mínimas);
* `unidades`: id, nome, nível (`estado`, `polo` ou `posto`), região, localidade, porta,
  host (opcional), capacidade, `abastece`, `vizinhos` e `alvo`;
* `localidades` (id, nome, latitude, longitude) e `trechos` (origem, destino, horas, meio).

A carga valida o arquivo (localidades e unidades existentes, portas repetidas, cada unidade
com no máximo um fornecedor) e torna a vizinhança simétrica.

Para rodar em máquinas diferentes, informe o `host` de cada unidade no arquivo e suba cada
nó com `python -m soro no <id> --escutar 0.0.0.0`.

## 12. Avaliação

`python -m soro avaliar` sobe os 8 nós em processos separados numa pasta temporária, com
sincronização a cada 0,5 s, e responde às quatro perguntas. Resultados de uma execução num
notebook com Intel i7-12700H (20 núcleos lógicos), em `resultados/avaliacao.json`:

| Pergunta | Como foi medida | Resultado |
|---|---|---|
| Falha de um nó | Polo Tabatinga encerrado; 10 atendimentos em cada um dos 3 postos dele | 30 de 30 aceitos; com o polo de volta, todos os nós iguais em 1,7 s |
| Dados iguais | 20 atendimentos ao mesmo tempo em cada um dos 8 nós | todos com o mesmo resumo em 1,7 s |
| Nada se perde | 10 atendimentos enviados duas vezes cada; contagem em todos os nós | 200 casos distintos em cada nó, nenhum perdido ou duplicado |
| Velocidade | postos críticos num mapa sintético de 14.400 localidades e 200 postos | 7,9 s com 1 processo; 2,0 s com 16 (3,9 vezes mais rápido) |

O ganho do paralelismo para em torno de 4 vezes porque o notebook reduz a frequência
sob carga e tem núcleos de desempenho e de eficiência. Os tempos de convergência
dependem do intervalo de sincronização e do número de saltos entre os nós.

## 13. Limitações

* Não há login nem criptografia entre nós. Numa implantação real, cada nó teria
  certificado próprio e a comunicação seria por HTTPS.
* O diário só cresce. Uma versão futura pode arquivar eventos antigos que todos os nós
  já têm (o mínimo dos vetores de versão conhecidos).
* O estado é recalculado a partir de todos os eventos quando chega algo novo. Para
  milhares de eventos é rápido; para anos de uso, seria preciso guardar saldos parciais.
* A idade da informação usa o relógio de cada nó. Relógios muito errados distorcem a
  idade mostrada, mas não afetam os dados.
* Um surto que atravessa a virada da semana pode gerar dois alertas.
* O que um nó sabe dos outros pode estar atrasado. O sistema não elimina isso; mostra a
  idade de cada dado para quem decide.
