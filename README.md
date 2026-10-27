# Orbe

Mesa de leitura de dossiês. A resposta em português cita o arquivo, o trecho e a posição. Se dois trechos se contradizem, os dois aparecem. Cada pergunta fica gravada com a resposta e as citações.

A versão `0.2.0` sobe a mesa local: recebe o arquivo, indexa o texto e responde a partir dos trechos recuperados.

## Iniciar

Na raiz do repositório:

```bash
./scripts/start.sh
```

A interface fica em http://127.0.0.1:8000/. O script executa `docker compose up --build` e não cria arquivo. Ele sobe o banco e a API juntos.

Exporte `OPENAI_API_KEY` no ambiente antes do script quando for indexar ou perguntar. Sem a chave, a página abre e a operação avisa a falta. `LANGSMITH_API_KEY` liga o rastreio somente quando também está presente. As chaves não entram em arquivo versionado.

`APP_ENV=production` recusa URL de banco sem host ou senha e recusa escutar em todas as interfaces.

Para rodar a API no host, com o banco do Compose já saudável:

```bash
docker compose up -d db
uv sync --frozen --all-groups
uv run python -m orbe
```

O healthcheck da imagem consulta `/health/live`. O healthcheck do Compose consulta `/health/ready`.

## O que esta versão faz

- Sobe a API e a página em `http://127.0.0.1:8000/` com `./scripts/start.sh`.
- Aceita PDF, Markdown e TXT. O nome gravado é o nome enviado, sem caminho.
- Rejeita o arquivo acima do limite enquanto o lê, antes de guardar tudo na memória. O teto padrão é 10 MiB (`DOCUMENT_MAX_BYTES`).
- Indexa fora do laço de eventos, então a vida, a prontidão e as perguntas leves continuam respondendo enquanto um arquivo grande entra. `INDEX_MAX_CONCURRENCY` limita quantos arquivos indexam ao mesmo tempo (padrão 2).
- Fragmenta o texto e grava os trechos no PostgreSQL com pgvector.
- Reconhece o mesmo conteúdo pelo hash e devolve o registro já existente. Uma indexação interrompida é retomada sem duplicar trechos: os trechos entram antes do registro e a repetição regrava as mesmas linhas.
- Responde a pergunta com os trechos cuja distância de cosseno fica dentro do limite.
- A citação traz o arquivo, a posição e o texto recuperado. Esse texto sai do índice, não da frase gerada.
- Se nenhum trecho fica perto da pergunta, a resposta é `O dossiê não cobre essa pergunta.` e o modelo de chat não é chamado.
- Grava a pergunta, a resposta e as citações.
- Recusa PDF sem texto. Não há OCR.

## Arquitetura

O processo é uma mesa única. A composição está em `src/orbe/api/app.py`. A configuração vem do ambiente e não depende do FastAPI. A rota de vida não consulta o banco. A prontidão consulta o PostgreSQL e a extensão `vector`.

A indexação valida o arquivo, extrai o texto, fragmenta e grava. A pergunta busca os trechos mais próximos. A cadeia de resposta só é chamada quando existe trecho dentro do limite, e recebe somente esses trechos. O prompt pede para mostrar os dois lados quando as fontes se contradizem, sem eleger um vencedor.

A página em `/` é HTML, CSS e JavaScript servidos pelo mesmo processo. Ela usa os mesmos contratos HTTP. A decisão de citar só o trecho recuperado está em [docs/adr/0001-citacoes-verificaveis.md](docs/adr/0001-citacoes-verificaveis.md). O fluxo de branches está em [CONTRIBUTING.md](CONTRIBUTING.md).

## Tecnologias

- Python 3.12
- FastAPI, Pydantic e Pydantic Settings
- LangChain e LangChain Postgres
- SQLAlchemy 2 e psycopg 3
- PostgreSQL 16 com pgvector 0.8.7
- pypdf, para texto de PDF
- uv 0.13
- pytest, Ruff e Mypy
- Docker Compose

As versões resolvidas estão em `uv.lock`.

## API

Não há autenticação. Esta API não está pronta para exposição pública.

- `GET /` — página local. Não entra no OpenAPI.
- `GET /health/live` — o processo responde. Não consulta o banco.
- `GET /health/ready` — o PostgreSQL responde e a extensão `vector` está instalada.
- `POST /api/v1/documents` — envia um arquivo no campo `file`. PDF, Markdown ou TXT. Responde `201` com `id`, `filename`, `chunk_count` e `duplicate`. O arquivo acima do teto é recusado durante a leitura.
- `GET /api/v1/documents` — lista os documentos indexados, do mais recente ao mais antigo, com `id`, `filename` e `chunk_count`.
- `DELETE /api/v1/documents/{id}` — apaga o documento e seus trechos do índice. Responde `204`, ou `404` se o `id` não existe. As perguntas já gravadas mantêm o trecho citado, que é um retrato do índice no momento da resposta.
- `POST /api/v1/queries` — corpo `{"question": "..."}`. Responde com `id`, `question`, `answer`, `grounded` e `citations`.

Toda resposta traz `X-Request-ID` (o valor enviado é reaproveitado, senão a mesa gera um) para correlacionar com os logs.

O contrato interativo está em `/docs`.

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS -D - http://127.0.0.1:8000/health/ready
curl -fsS -F "file=@dossie.md;type=text/markdown" http://127.0.0.1:8000/api/v1/documents
curl -fsS -H "Content-Type: application/json" \
  -d '{"question":"qual o prazo?"}' \
  http://127.0.0.1:8000/api/v1/queries
```

Cada citação traz `filename`, `position`, `content` e `distance`. A pergunta fica gravada.

Erros usam `application/problem+json`. Uma falha interna devolve uma mensagem genérica. O corpo não inclui traceback, senha ou URL do banco.

## Testes

A suíte completa exige PostgreSQL local com pgvector. O host aceito é `localhost`, `127.0.0.1`, `::1` ou `db`.

```bash
docker compose up -d db
export APP_ENV=test
export DATABASE_URL=postgresql+psycopg://orbe:orbe@127.0.0.1:5432/orbe
uv run ruff format --check
uv run ruff check
uv run mypy
uv run pytest --cov-fail-under=85
uv run pip-audit --progress-spinner off
```

A cobertura exigida é 85% do pacote `orbe`, com medição de ramos. A CI ainda constrói a imagem e a escaneia com Trivy, falhando em vulnerabilidade `HIGH`/`CRITICAL` que tenha correção.

## Backup e recuperação

Com o banco do Compose no ar:

```bash
./scripts/backup.sh                       # gera backups/orbe-<data>.dump
./scripts/restore.sh backups/orbe-<data>.dump   # restaura em orbe_restore
```

O `restore.sh` nunca escreve sobre o banco de uso: ele cria um banco novo (padrão `orbe_restore`) e recusa `orbe` como destino. Antes de promover, aponte `DATABASE_URL` para o banco restaurado e valide pela aplicação. Os códigos de saída são `0` sucesso, `1` falha e `2` inconclusivo.

## Limitações

- Não há autenticação nem autorização. A mesa escuta em `127.0.0.1` por padrão e o Compose publica a porta só no loopback. Quem alcança o processo alcança todo o acervo; expor para uma rede exige identidade e ACL por dossiê, que esta versão não traz.
- `DELETE /api/v1/documents/{id}` remove o documento e seus trechos do índice, então ele não aparece mais nas respostas futuras. A exclusão não apaga as perguntas já gravadas: cada resposta guarda o retrato do trecho que citou. Não há ainda política de retenção por prazo para o histórico.
- PDF digitalizado, sem texto, é recusado. Não há OCR.
- A coluna vetorial está fixada em 1536 dimensões para `text-embedding-3-small`.
- As credenciais do Compose são de desenvolvimento. Não as reutilize fora da máquina local.
- A tag desta versão é `v0.2.0`.
