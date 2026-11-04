# Instruções para agentes — AMpolo

## Diretrizes do projeto

Leia e siga `project_guidelines.md` antes de propor ou implementar mudanças.

Este repositório contém a aplicação da equipe de saúde e gestão.
O aplicativo dos cidadãos pertence a outro repositório.

## Skill obrigatória para frontend

Sempre utilize a skill `frontend-design` em tarefas que envolvam:

- Criação ou alteração de telas.
- Componentes Vue e layouts.
- Estilização com Tailwind CSS.
- Tipografia, cores, espaçamento e responsividade.
- Formulários, navegação e estados da interface.
- Revisão visual ou propostas de experiência do usuário.

Leia as instruções em:

`.agents/skills/frontend-design/SKILL.md`

Aplique a skill também quando entregar somente exemplos ou código no chat,
sem modificar arquivos.

Se o arquivo não estiver disponível, informe essa condição antes de
prosseguir com o trabalho visual.

## Identidade visual

Preserve a identidade estabelecida, salvo orientação explícita do usuário:

- Fonte principal: Red Hat Text.
- Verde rio: `#2A6F5E`.
- Verde mata: `#0D3F34`.
- Texto principal: `#111A17`.
- Fundo: `#F5F7F6`.
- Superfície suave: `#EAF2EE`.
- Texto secundário: `#65716B`.
- Bordas: `#DCE4DF`.

Reutilize os tokens existentes no CSS e os componentes do projeto.

A aplicação deve transmitir clareza, confiança e organização operacional.
Priorize a leitura de estoques, remessas, atendimentos e alertas.

## Processo de design

Antes de apresentar uma solução visual:

1. Identifique o público, a tarefa e o contexto da tela.
2. Examine as referências e os componentes existentes.
3. Defina brevemente a hierarquia, o layout e os estados necessários.
4. Revise a proposta conforme a skill e as instruções do usuário.
5. Entregue o código ou implemente apenas dentro do escopo autorizado.

A profundidade do planejamento deve acompanhar o tamanho da tarefa.
Ajustes pequenos não exigem redesenhar a interface.

## Qualidade da interface

- Use HTML semântico, campos com rótulos e foco visível.
- Garanta navegação por teclado.
- Preserve contraste e legibilidade.
- Não comunique situações apenas por cor.
- Considere carregamento, erro, ausência de dados e sucesso.
- Respeite a preferência por movimento reduzido.
- Use textos em português claros e orientados à ação.
- Diferencie dados demonstrativos de dados reais.
- Exiba a idade das informações de outras unidades quando aplicável.
- Não apresente recomendações de doses ou condutas clínicas.

Quando houver implementação e ferramentas disponíveis, verifique a
interface em tamanhos de tela relevantes. Informe o que não foi validado.

## Organização e tecnologias

- Vue 3 com Composition API e TypeScript.
- Tailwind CSS para estilização.
- Vue Router para navegação.
- Siga a estrutura e a nomenclatura de `project_guidelines.md`.
- Preserve a separação entre apresentação, domínio e integração HTTP.
- Reutilize dependências existentes antes de propor novas.

## Autorização para alterações

Por padrão, entregue orientações e códigos no chat.

Não crie, edite, exclua arquivos, instale dependências ou execute operações
que alterem dados sem uma solicitação explícita para realizar essas ações.

Pedidos para explicar, revisar, sugerir ou fornecer código não autorizam
alterações no repositório.

## Prioridade das instruções

As instruções explícitas do usuário prevalecem sobre as recomendações
visuais da skill.

A skill orienta o trabalho de frontend; não amplia o escopo autorizado
nem exige alterações de backend para tarefas exclusivamente visuais.