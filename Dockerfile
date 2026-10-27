FROM python:3.12.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable --python /usr/local/bin/python3


FROM python:3.12.12-slim-bookworm AS runtime

# Pull the latest Debian security patches for the base OS packages (openssl, perl,
# etc.) so the shipped image does not carry fixed base-image CVEs.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 orbe \
    && useradd --system --uid 10001 --gid orbe --create-home --home-dir /home/orbe orbe

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
