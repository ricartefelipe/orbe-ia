"""HTTP routes for health, documents, questions, and the local page."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response

from orbe.api.schemas import AnswerBody, CitationBody, DocumentBody, DocumentSummary, QueryIn
from orbe.domain.errors import UnreadableDossier
from orbe.infrastructure.readiness import database_ready

_UPLOAD_CHUNK = 1024 * 1024

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


async def _read_within_limit(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks and stop as soon as it passes the limit.

    The oversized body is rejected before the whole file is held in memory, so a
    chunked request without a declared length cannot be used to exhaust it.
    """

    buffer = bytearray()
    while chunk := await file.read(_UPLOAD_CHUNK):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise UnreadableDossier("O arquivo excede o tamanho permitido.")
    return bytes(buffer)


@router.post("/api/v1/documents", status_code=201)
async def create_document(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> DocumentBody:
    """Index one dossier file."""

    settings = request.app.state.settings
    async with request.app.state.index_semaphore:
        content = await _read_within_limit(file, settings.document_max_bytes)
        # Indexing parses the file, calls the embedding model, and writes to the
        # database. Running it on a worker thread keeps the event loop free to
        # answer health checks and light questions while a large file indexes.
        indexed = await run_in_threadpool(
            request.app.state.indexer.index, file.filename or "", content
        )
    return DocumentBody(
        id=indexed.id,
        filename=indexed.filename,
        chunk_count=indexed.chunk_count,
        duplicate=indexed.duplicate,
    )


@router.get("/api/v1/documents")
def list_documents(request: Request) -> list[DocumentSummary]:
    """List the indexed files, most recent first."""

    return [
        DocumentSummary(id=record.id, filename=record.filename, chunk_count=record.chunk_count)
        for record in request.app.state.indexer.list()
    ]


@router.delete("/api/v1/documents/{document_id}", status_code=204)
async def delete_document(request: Request, document_id: UUID) -> Response:
    """Delete a dossier file and its excerpts. Answered questions keep their snapshots."""

    await run_in_threadpool(request.app.state.indexer.remove, document_id)
    return Response(status_code=204)


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
