# Contribuir

## Fluxo de branches

O repositório usa GitFlow.

| Branch | Origem | Destino da integração |
| --- | --- | --- |
| `main` | release ou hotfix | Estado publicável. |
| `develop` | feature, release ou hotfix | Integração ainda não publicada. |
| `feature/<nome>` | `develop` | Pull request com base `develop`. |
| `release/<versao>` | `develop` | `main` e, em seguida, `develop`. |
| `hotfix/<nome>` | `main` | `main` e, em seguida, `develop`. |

A pipeline recusa pull request fora dessa tabela.

### Integrar

1. Crie a branch de trabalho a partir da origem atualizada.
2. Abra o pull request para o destino da tabela.
3. Integre com merge commit, sem fast-forward, sem squash e sem rebase.
4. Apague a branch de trabalho, local e remota, no mesmo ato.

Para integrar localmente:

```bash
git checkout develop
git merge --no-ff feature/<nome>
git branch -d feature/<nome>
```

`release/*` e `hotfix/*` voltam para `main` e para `develop` antes de serem apagadas.

Não use force push.

## Commits

Use Conventional Commits. Adicione arquivos individualmente. Não use `git add .` nem `git add -A`.

A mensagem fica no imperativo, sem assinatura, sem `Co-authored-by` e sem `Signed-off-by`.

## Qualidade

```bash
uv sync --frozen --all-groups
uv run ruff format --check
uv run ruff check
uv run mypy
uv run pytest --cov-fail-under=85
```

A suíte de integração precisa de PostgreSQL com pgvector, no banco `orbe` ou `orbe_test`, em host local.
