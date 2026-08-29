# Joanna — MVP de assistente de agenda

Uma secretária digital simples: converse em português, consulte o Google Calendar e crie eventos. O MVP usa FastAPI, Google Calendar API, OAuth 2.0 e OpenAI.

## O que este MVP faz

- Consulta eventos em tempo real (`O que eu tenho amanhã?`).
- Cria eventos quando data e horário estão claros (`Adicione uma reunião com João amanhã às 14h`).
- Busca, altera e solicita confirmação antes de excluir eventos.
- Trata horários no fuso `America/Sao_Paulo`.

É uma aplicação **local e para uma única conta Google**. O token OAuth é salvo localmente em `data/token.json`, fora do Git. Não há senha Google armazenada, banco de dados ou recursos fora do escopo do MVP.

## 1. Pré-requisitos

- Python 3.11 ou superior.
- Uma chave da OpenAI API.
- Uma conta Google e um projeto no Google Cloud.

## 2. Configurar Google Calendar API e OAuth

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/) e crie ou selecione um projeto.
2. Em **APIs e serviços > Biblioteca**, habilite **Google Calendar API**.
3. Em **APIs e serviços > Tela de consentimento OAuth**, configure a tela. Para teste, adicione seu e-mail em **Usuários de teste**.
4. Em **Credenciais**, crie **ID do cliente OAuth** do tipo **Aplicativo da Web**.
5. Em **URIs de redirecionamento autorizados**, adicione a URI indicada na sua configuração. Para Docker, siga a seção Docker abaixo para obter a porta aleatória antes de cadastrá-la.
6. Copie o Client ID e o Client Secret gerados.

## 3. Configurar variáveis

```bash
cp .env.example .env
```

Edite `.env` e preencha `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`. Mantenha `GOOGLE_REDIRECT_URI` igual à URI cadastrada no Google Cloud. Para execução local, use `http://localhost:8000/auth/google/callback`. Você pode alterar `OPENAI_MODEL` para um modelo disponível na sua conta.

## 4. Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra [http://localhost:8000](http://localhost:8000), clique em **Conectar Google Calendar**, entre na sua conta Google e autorize o acesso. O token será criado em `data/token.json` com permissão somente para seu usuário local.

## 5. Testar

Após conectar o calendário, tente:

- `Quais são meus compromissos de amanhã?`
- `Adicione uma reunião com João amanhã às 14h.`
- `Crie um compromisso chamado Dentista sexta-feira às 10h.`
- `Apague minha reunião das 15h.` — a assistente deverá pedir confirmação antes de excluir.

Para executar os testes automatizados (eles não chamam APIs externas):

```bash
pytest
```

## Docker

O Docker é suficiente para executar a aplicação; você não precisa instalar Python nem as dependências do projeto na máquina. A porta interna do container continua `8000`, mas o Compose escolhe automaticamente uma porta efêmera disponível no `localhost`, evitando conflitos com outros containers.

1. Crie o arquivo de configuração e preencha as credenciais:

   ```bash
   cp .env.example .env
   ```

2. Inicie o container em segundo plano e descubra a porta escolhida:

   ```bash
   docker compose up --build -d
   ./scripts/docker-port
   ```

   O último comando imprime apenas a porta, por exemplo `49153`. Alternativamente, use `docker compose port app 8000`.

3. Troque `REPLACE_WITH_DOCKER_PORT` em `.env` pela porta impressa, por exemplo:

   ```dotenv
   GOOGLE_REDIRECT_URI=http://localhost:49153/auth/google/callback
   ```

   Cadastre exatamente essa mesma URI em **Google Cloud Console > Credenciais > URIs de redirecionamento autorizados** e reinicie para aplicar a alteração:

   ```bash
   docker compose up -d --force-recreate
   ```

4. Abra `http://localhost:<porta>` no navegador. Para acompanhar os logs, execute `docker compose logs -f app`; para encerrar, execute `docker compose down`.

O volume `./data` mantém o token OAuth entre reinicializações. Como a porta publicada é escolhida novamente quando o container é recriado, repita os passos 2 e 3 se o Compose atribuir uma nova porta; isso mantém o redirecionamento OAuth consistente com a URL cadastrada no Google.

## Limites intencionais

Este MVP não implementa múltiplos usuários, banco de dados, WhatsApp, voz, e-mail, tarefas, memória de longo prazo, notificações, outros calendários ou automações. Para uso em produção, substitua o token local por armazenamento seguro e implemente autenticação de usuários.
