"""Problem details for expected and unexpected failures."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from orbe.domain.errors import (
    DossierNotFound,
    InvalidQuestion,
    MissingOpenAIKey,
    ModelCallFailed,
    UnreadableDossier,
)
from orbe.logging import log_failure

_UNEXPECTED = "A mesa não conseguiu concluir a operação."


def problem(status: int, detail: str, title: str) -> JSONResponse:
    """Return an RFC 9457 problem without echoing the request body."""

    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Map desk failures to problem responses."""

    @app.exception_handler(MissingOpenAIKey)
    async def missing_key(_request: Request, exc: MissingOpenAIKey) -> JSONResponse:
        return problem(503, str(exc), "Serviço indisponível")

    @app.exception_handler(UnreadableDossier)
    async def unreadable(_request: Request, exc: UnreadableDossier) -> JSONResponse:
        return problem(422, str(exc), "Arquivo ilegível")

    @app.exception_handler(InvalidQuestion)
    async def invalid_question(_request: Request, exc: InvalidQuestion) -> JSONResponse:
        return problem(422, str(exc), "Pergunta inválida")

    @app.exception_handler(DossierNotFound)
    async def not_found(_request: Request, exc: DossierNotFound) -> JSONResponse:
        return problem(404, str(exc), "Documento não encontrado")

    @app.exception_handler(ModelCallFailed)
    async def model_failed(_request: Request, exc: ModelCallFailed) -> JSONResponse:
        return problem(502, str(exc), "Falha do modelo")

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return problem(422, "A requisição não pôde ser lida.", "Requisição inválida")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else _UNEXPECTED
        return problem(exc.status_code, detail, "Erro HTTP")

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception) -> JSONResponse:
        log_failure(type(exc).__name__)
        return problem(500, _UNEXPECTED, "Erro interno")
