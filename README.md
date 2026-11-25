# HelpDesk TI — Arquitetura de Microsserviços

**Atividade individual — Arquitetura de Software**

> **Vídeo obrigatório (4 a 6 minutos):** ainda precisa ser gravado e publicado pelo aluno. Insira aqui o link não listado do YouTube ou do Google Drive antes da entrega.

Este repositório parte do monólito disponibilizado pelo professor e o reorganiza em serviços independentes, mantendo a tela web e as rotas usadas pelo navegador.

## Arquitetura

~~~mermaid
flowchart TB
    Browser[Interface Web] -->|HTTP :8000| GW[API Gateway]
    GW -->|/auth e /usuarios| U[Serviço de Usuários]
    GW -->|/ativos| I[Serviço de Inventário]
    GW -->|/chamados| C[Serviço de Chamados]
    C -->|HTTP + JWT| U
    C -->|HTTP + JWT| I
    U --> DBU[(usuarios.db)]
    I --> DBI[(inventario.db)]
    C --> DBC[(chamados.db)]
~~~

### Responsabilidades

| Componente | Responsabilidade | Persistência |
|---|---|---|
| Gateway | Ponto único de entrada, proxy HTTP, arquivos da interface e saúde agregada | Sem banco |
| Usuários | Login, JWT, perfis, listagem e consulta de usuários | Banco próprio |
| Inventário | Cadastro e consulta de ativos | Banco próprio |
| Chamados | Abertura, atribuição, status, comentários, SLA e painel | Banco próprio |

Os IDs de solicitante, técnico e ativo são referências lógicas no banco de Chamados, não chaves estrangeiras entre serviços. O relacionamento de comentários com chamados continua local ao serviço de Chamados.

## Como executar

Pré-requisitos: Docker Desktop (com Docker Compose) e Git.

1. Clone este repositório.
2. Copie .env.example para .env e substitua JWT_SEGREDO por uma chave aleatória com pelo menos 32 caracteres.
3. Na pasta do projeto, execute:

~~~bash
docker compose up --build
~~~

A interface ficará em **http://localhost:8000**. Para ver os contêineres:

~~~bash
docker compose ps
~~~

Para parar tudo: docker compose down. Os bancos persistem em volumes Docker separados.

> Apenas o Gateway publica a porta 8000 no host. Os serviços e bancos ficam na rede interna do Compose e não publicam portas externas.

## Contas de demonstração

Senha padrão de demonstração: Helpdesk2026 (pode ser alterada em SENHA_EXEMPLO no .env).

| Perfil | E-mail |
|---|---|
| Administrador | admin@empresa.com |
| Solicitante | ana@empresa.com |
| Solicitante | bruno@empresa.com |
| Técnica | carla@empresa.com |
| Técnico | diego@empresa.com |

## Rotas principais

Todas as chamadas do navegador passam pelo Gateway:

- POST /auth/login e GET /auth/eu
- GET /usuarios e GET /usuarios/{id}
- GET /ativos e GET /ativos/{id}
- POST /chamados, GET /chamados, GET /chamados/painel
- PATCH /chamados/{id}/atribuir e PATCH /chamados/{id}/status
- POST /chamados/{id}/comentarios
- GET /notificacoes
- GET /saude — visão agregada da saúde dos três serviços

As regras de SLA e transições permanecem no serviço de Chamados. Solicitantes veem apenas os próprios chamados; equipe técnica pode consultar todos. Chamados resolvidos podem ser fechados ou reabertos conforme as regras originais.

## Comunicação entre serviços e falhas

Ao abrir um chamado com ativo, Chamados consulta GET /ativos/{id} no Inventário. Ao atribuir, consulta GET /usuarios/{id} em Usuários e confirma o perfil técnico. As duas chamadas usam o cabeçalho Authorization recebido do cliente e têm timeout de 2,5 segundos. Falha de conexão/timeout retorna HTTP 503 com mensagem clara; registro inexistente retorna 404.

Para demonstrar a tolerância a falhas:

~~~bash
docker compose stop inventario
~~~

A lista de usuários e chamados continua disponível. A abertura de chamado que referencie um ativo deve retornar 503 sem ficar aguardando indefinidamente. Depois, restaure o serviço:

~~~bash
docker compose start inventario
~~~

## Segurança

- Todos os serviços validam assinatura, emissor e expiração do JWT localmente.
- A chave JWT_SEGREDO é injetada pelo ambiente/arquivo .env, não fica no código-fonte.
- A autorização por perfil é verificada nas rotas protegidas.
- O Gateway é o único componente exposto ao host.
- Os contêineres usam usuário não-root, filesystem somente leitura, no-new-privileges e removem capabilities.
- O Gateway não altera o cabeçalho Authorization ao encaminhar requisições.

## Testes

O conjunto original do monólito permanece em tests/ como regressão das regras de negócio:

~~~bash
pip install -r requirements-dev.txt
pytest -q
~~~

## Decisões e limitações conhecidas

- A separação foi feita com quatro entrypoints FastAPI, um por aplicação, e um banco SQLite em volume separado para cada serviço de domínio.
- O código compartilhado de autenticação e validação fica no pacote app/auth; cada serviço valida o JWT com o mesmo segredo, sem consultar a tabela de usuários em outro banco.
- Notificações seguem armazenadas junto ao serviço de Chamados nesta versão. A fila assíncrona (Redis/RabbitMQ) e o consumidor de Notificações são extensões bônus ainda não implementadas.
- O vídeo de demonstração é uma etapa manual obrigatória: grave o fluxo da interface, a falha controlada do Inventário, os bancos separados e o estado dos contêineres; depois substitua o aviso no início deste README pelo link.

## Histórico da origem

Projeto-base: prof-filipecavalcante/helpdesk-ti. Requisitos completos da atividade em DESAFIO.md.
