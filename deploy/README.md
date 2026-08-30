# Deploy automático (GitHub Actions → VPS)

A cada push na branch `main`, o workflow [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml):

1. **`test`** — instala as dependências e roda `pytest`. Se falhar, o deploy nem começa.
2. **`deploy`** — conecta na VPS via SSH e executa:
   ```
   cd ~/apps/joanna-assistant
   git fetch --prune origin && git reset --hard origin/main
   docker compose up --build -d --remove-orphans
   # health check em http://127.0.0.1:5089/api/config (até ~60s)
   docker image prune -f
   ```

O health check bate direto no container (`127.0.0.1:5089`), então não depende do
Nginx nem de autenticação. Se a aplicação não responder, o job **falha** e os
últimos logs do container aparecem na saída da Action.

> `git reset --hard origin/main` (em vez de `git pull`) torna o deploy
> determinístico. Ele **não toca** em arquivos fora do git — `.env` e `data/`
> ficam intactos (só `git clean` apagaria não rastreados, e nós não rodamos).

## Configuração única

### 1. Gerar uma chave SSH dedicada ao deploy

Na **sua máquina** (não na VPS):

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy-joanna" -f ~/.ssh/joanna_deploy -N ""
```

Isso cria `~/.ssh/joanna_deploy` (privada) e `~/.ssh/joanna_deploy.pub` (pública).

### 2. Autorizar a chave pública na VPS

```bash
ssh-copy-id -i ~/.ssh/joanna_deploy.pub oscar@191.252.219.228
# ou, manualmente:
cat ~/.ssh/joanna_deploy.pub | ssh oscar@191.252.219.228 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

Teste: `ssh -i ~/.ssh/joanna_deploy oscar@191.252.219.228 'echo ok && cd ~/apps/joanna-assistant && git status'`

### 3. Criar os GitHub Secrets

Em **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor |
|---|---|
| `SSH_HOST` | `191.252.219.228` |
| `SSH_USER` | `oscar` |
| `SSH_PRIVATE_KEY` | conteúdo **completo** de `~/.ssh/joanna_deploy` (com as linhas `BEGIN`/`END`) |
| `SSH_PORT` | *(opcional — só se o SSH não for na 22)* |

Via CLI (na raiz do repo):

```bash
gh secret set SSH_HOST --body "191.252.219.228"
gh secret set SSH_USER --body "oscar"
gh secret set SSH_PRIVATE_KEY < ~/.ssh/joanna_deploy
```

## Primeiro deploy automático

Depois dos secrets criados: faça um commit trivial na `main` (ou use
**Actions → Deploy → Run workflow**) e acompanhe em **Actions**.

## Rollback manual

```bash
ssh oscar@191.252.219.228
cd ~/apps/joanna-assistant
git reset --hard <sha-anterior>
docker compose up --build -d
```
