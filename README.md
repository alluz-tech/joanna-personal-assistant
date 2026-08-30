# Joanna — MVP de assistente de agenda

Uma secretária digital simples: converse em português, consulte o Google Calendar e crie eventos. O MVP usa FastAPI, Google Calendar API, OAuth 2.0 e OpenAI.

## O que este MVP faz

- **Conversa**: converse em português para consultar eventos (`O que eu tenho amanhã?`),
  criar (`Adicione uma reunião com João amanhã às 14h`), alterar e excluir (com confirmação).
  A conversa mantém o contexto entre as mensagens — você pode responder "sim", "próxima segunda"
  ou "das 16h às 17h" sem repetir o resto.
- **Voz**: com o campo de texto vazio, toque no **botão de microfone** para começar a gravar.
  Durante a gravação aparecem dois botões: **enviar** (avião de papel) ou **cancelar** (X).
  A Joanna transcreve o áudio (`OPENAI_TRANSCRIBE_MODEL`), passa pelo mesmo agente da conversa
  por texto e responde também em áudio (`OPENAI_TTS_MODEL` / `OPENAI_TTS_VOICE`), que **toca
  automaticamente**; um botão permite reouvir. Antes de falar, datas e horários abreviados
  são expandidos (`31/08` → "31 de agosto", `14h30` → "14 horas e 30") para o TTS não
  soletrar a pontuação. O texto exibido na conversa continua no formato curto.
- **Agenda**: uma segunda tela (navegação no topo, SPA) com o calendário estilo Google Agenda
  nas visões **Mês**, **Semana** e **Dia**, filtros (busca livre, participante, faixa de horário,
  intervalo de datas, só dia inteiro, só com participantes) e criação/edição/exclusão direto
  pelo calendário — clique num horário para criar, num evento para editar.
- **Acesso por PIN**: a cada carregamento da página aparece um teclado numérico. Digite o
  código (`JOANNA_PIN`, padrão `278395`) para liberar o app. Sem o PIN, as rotas de dados
  (`/api/...` e o OAuth) respondem `401`. A liberação é um cookie de sessão assinado, com
  segredo sorteado a cada início do servidor — reiniciar ou fechar o navegador pede o PIN de novo.
- Trata horários no fuso `America/Sao_Paulo`.
- Interface limpa com **tema claro/escuro** (segue o sistema; botão no canto superior direito
  alterna e memoriza a preferência) e layout responsivo para celular e tablet.

### Avatar da Joanna (opcional)

Coloque uma imagem em `app/static/joanna.png` (quadrada, ~256×256 ou maior) para usá-la
como rosto da assistente na tela de Conversa. Sem o arquivo, é exibido um ícone padrão.

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
5. Em **URIs de redirecionamento autorizados**, adicione a URI indicada na sua configuração. Para Docker, use `http://localhost:5089/auth/google/callback`.
6. Copie o Client ID e o Client Secret gerados.

## 3. Configurar variáveis

```bash
cp .env.example .env
```

Edite `.env` e preencha `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`. Mantenha `GOOGLE_REDIRECT_URI` igual à URI cadastrada no Google Cloud. Para execução local, use `http://localhost:8000/auth/google/callback`. Você pode alterar `OPENAI_MODEL` para um modelo disponível na sua conta.

Para a conversa por voz, `OPENAI_TRANSCRIBE_MODEL`, `OPENAI_TTS_MODEL` e `OPENAI_TTS_VOICE` são opcionais e já têm padrões (`gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`, `shimmer`). O microfone exige um contexto seguro no navegador (`localhost` ou HTTPS).

`JOANNA_PIN` é o código da tela de acesso (padrão `278395`). Troque por um código só seu — mantê-lo no `.env` evita deixá-lo no código versionado.

## 4. Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra [http://localhost:8000](http://localhost:8000), clique em **Conectar Google Calendar**, entre na sua conta Google e autorize o acesso. O token será criado em `data/token.json` com permissão somente para seu usuário local.

## 5. Testar

Após conectar o calendário, na aba **Conversa** tente:

- `Quais são meus compromissos de amanhã?`
- `Adicione uma reunião com João amanhã às 14h.`
- `Crie um compromisso chamado Dentista sexta-feira às 10h.`
- `Apague minha reunião das 15h.` — a assistente deverá pedir confirmação antes de excluir.

Na aba **Agenda**, navegue entre Mês/Semana/Dia, use os filtros da lateral e clique
no calendário para criar ou editar um compromisso.

Para executar os testes automatizados (eles não chamam APIs externas):

```bash
pytest
```

## Docker

O Docker é suficiente para executar a aplicação; você não precisa instalar Python nem as dependências do projeto na máquina. A porta interna do container continua `8000` e é publicada na porta fixa `5089` do `localhost`.

1. Crie o arquivo de configuração e preencha as credenciais:

   ```bash
   cp .env.example .env
   ```

2. Inicie o container em segundo plano:

   ```bash
   docker compose up --build -d
   ```

3. Cadastre `http://localhost:5089/auth/google/callback` em **Google Cloud Console > Credenciais > URIs de redirecionamento autorizados**.

4. Abra [http://localhost:5089](http://localhost:5089) no navegador. Para acompanhar os logs, execute `docker compose logs -f app`; para encerrar, execute `docker compose down`.

O volume `./data` mantém o token OAuth entre reinicializações.

## Limites intencionais

Este MVP não implementa múltiplos usuários, banco de dados, WhatsApp, voz, e-mail, tarefas, memória de longo prazo, notificações, outros calendários ou automações. Para uso em produção, substitua o token local por armazenamento seguro e implemente autenticação de usuários.
