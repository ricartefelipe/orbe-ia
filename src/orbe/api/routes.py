"""HTTP routes for health, documents, questions, and the local page."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from orbe.api.schemas import AnswerBody, CitationBody, DocumentBody, QueryIn
from orbe.infrastructure.readiness import database_ready

_ASSETS = Path(__file__).resolve().parent.parent / "interface" / "assets"
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)
_ASSET_TYPES = {"app.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8"}

router = APIRouter()
page_router = APIRouter(include_in_schema=False)


@router.get("/health/live")
def live() -> dict[str, str]:
    """Process is up. This check does not touch the database or the model."""

    return {"status": "live"}


@router.get("/health/ready")
def ready(request: Request) -> Response:
    """Database and the vector extension are reachable."""

    if not database_ready(request.app.state.engine):
        return Response(
            status_code=503,
            media_type="application/problem+json",
            content=(
                '{"type":"about:blank","title":"Serviço indisponível",'
                '"status":503,"detail":"O banco não está pronto."}'
            ),
        )
    return Response(
        status_code=200,
        media_type="application/json",
        content='{"status":"ready"}',
    )


@router.post("/api/v1/documents", status_code=201)
async def create_document(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> DocumentBody:
    """Index one dossier file."""

    content = await file.read()
    indexed = request.app.state.indexer.index(file.filename or "", content)
    return DocumentBody(
        id=indexed.id,
        filename=indexed.filename,
        chunk_count=indexed.chunk_count,
        duplicate=indexed.duplicate,
    )


@router.post("/api/v1/queries")
def create_query(request: Request, body: QueryIn) -> AnswerBody:
    """Answer a question and return the retrieved citations."""

    asked = request.app.state.reader.ask(body.question)
    return AnswerBody(
        id=asked.id,
        question=asked.question,
        answer=asked.answer,
        grounded=asked.grounded,
        citations=[
            CitationBody(
                filename=citation.filename,
                position=citation.position,
                content=citation.content,
                distance=citation.distance,
            )
            for citation in asked.citations
        ],
    )


@page_router.get("/")
def page() -> HTMLResponse:
    """Local reading desk."""

    html = (_ASSETS / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html, headers={"Content-Security-Policy": _CSP})


@page_router.get("/assets/{name}")
def asset(name: str) -> Response:
    """Stylesheet or script for the local page."""

    media_type = _ASSET_TYPES.get(name)
    if media_type is None:
        return Response(status_code=404)
    body = (_ASSETS / name).read_text(encoding="utf-8")
    return Response(content=body, media_type=media_type)


@page_router.get("/favicon.ico", status_code=204)
def favicon() -> Response:
    """No icon. Keeps the browser from logging a missing file."""

    return Response(status_code=204)
