# Base Alpine (musl) por digest: menos pacotes de SO e correções publicadas aplicadas no build.
# python:3.12.12-alpine3.22
FROM python@sha256:848ba4413eb897e225159b8fc1b02094576cbae4aa73fc13142608ae2c8c0e32 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Instalação congelada pelo uv.lock (wheels musllinux para psycopg[binary], pydantic-core, numpy, tiktoken).
RUN uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python3


FROM python@sha256:848ba4413eb897e225159b8fc1b02094576cbae4aa73fc13142608ae2c8c0e32 AS runtime

# Correções de segurança publicadas para a base; ca-certificates para TLS de saída (provedor OpenAI-compatível).
RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates

RUN addgroup -S -g 10001 orbe \
    && adduser -S -u 10001 -G orbe -h /home/orbe orbe

WORKDIR /app

COPY --from=builder --chown=orbe:orbe /app/.venv /app/.venv
COPY --chown=orbe:orbe scripts/entrypoint.sh ./scripts/entrypoint.sh

USER orbe

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=local \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')"

ENTRYPOINT ["sh", "scripts/entrypoint.sh"]
