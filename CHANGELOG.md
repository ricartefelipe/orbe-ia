# Changelog

## 0.2.0 - 2026-10-27

- O envio acima do teto é recusado durante a leitura, antes de materializar o arquivo inteiro na memória.
- A indexação roda fora do laço de eventos; a vida, a prontidão e as perguntas leves seguem respondendo durante um envio grande. `INDEX_MAX_CONCURRENCY` limita quantos arquivos indexam ao mesmo tempo.
- A indexação é idempotente pelo conteúdo: uma queda no meio é retomada sem duplicar trechos.
- `DELETE /api/v1/documents/{id}` apaga o documento e seus trechos do índice. As perguntas já gravadas mantêm o retrato do trecho citado.
- `GET /api/v1/documents` lista o acervo; a página mostra os documentos e permite excluir cada um.
- A cadeia trata as fontes como dados, não instruções: texto malicioso dentro de um documento não altera as regras da resposta.
- Toda resposta traz `X-Request-ID` e os logs carregam esse id. `OPENAI_MAX_RETRIES` controla as novas tentativas do provedor.
- `scripts/backup.sh` e `scripts/restore.sh` fazem backup e restauram em um banco novo, sem tocar no banco de uso.
- A CI escaneia a imagem com Trivy, falhando em vulnerabilidade com correção. O Dockerfile atualiza os pacotes do SO para fechar CVEs da base.
- Atualiza `pypdf`, `certifi` e `filelock` para versões sem as vulnerabilidades apontadas pela auditoria.

## 0.1.1 - 2026-10-12

- O arranque da mesa fica em `./scripts/start.sh`, sem criar arquivo.

## 0.1.0 - 2026-10-12

- Indexa PDF, Markdown e TXT com LangChain e pgvector.
- Responde com citações tiradas dos trechos recuperados.
- Recusa pergunta sem trecho próximo e grava a leitura.
