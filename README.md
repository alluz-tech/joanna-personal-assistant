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
5. Em **URIs de redirecionamento autorizados**, adicione `http://localhost:8000/auth/google/callback`.
6. Copie o Client ID e o Client Secret gerados.

## 3. Configurar variáveis

```bash
cp .env.example .env
```

Edite `.env` e preencha `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`. Mantenha `GOOGLE_REDIRECT_URI` igual à URI cadastrada no Google Cloud. Você pode alterar `OPENAI_MODEL` para um modelo disponível na sua conta.

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

## Docker (opcional)

Com `.env` configurado, execute:

```bash
docker compose up --build
```

O volume `./data` mantém o token OAuth entre reinicializações. Se rodar em Docker, continue usando `http://localhost:8000/auth/google/callback` como URI de redirecionamento.

## Limites intencionais

Este MVP não implementa múltiplos usuários, banco de dados, WhatsApp, voz, e-mail, tarefas, memória de longo prazo, notificações, outros calendários ou automações. Para uso em produção, substitua o token local por armazenamento seguro e implemente autenticação de usuários.
