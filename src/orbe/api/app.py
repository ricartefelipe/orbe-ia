"""FastAPI application assembly."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from orbe import __version__
from orbe.api.errors import register_error_handlers
from orbe.api.routes import page_router, router
from orbe.application.reading import DossierIndexer, DossierReader
from orbe.config.settings import Settings, get_settings
from orbe.infrastructure.chat import OpenAIAnswerChain
from orbe.infrastructure.embeddings import OpenAIEmbeddingAdapter
from orbe.infrastructure.history import SqlReadingHistory
from orbe.infrastructure.keys import require_openai_key
from orbe.infrastructure.readiness import prepare_database
from orbe.infrastructure.tracing import configure_tracing
from orbe.infrastructure.vector_store import PgExcerptStore
from orbe.logging import configure_logging, log_request, set_request_id


def build_engine(settings: Settings) -> Engine:
    """Create a SQLAlchemy engine. The connection waits for the first use."""

    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        connect_args={"connect_timeout": settings.db_connect_timeout},
    )


def build_app(
    settings: Settings | None = None,
    indexer: DossierIndexer | None = None,
    reader: DossierReader | None = None,
    engine: Engine | None = None,
) -> FastAPI:
    """Assemble the desk. OpenAI clients stay unbuilt until an operation needs them."""

    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved.log_level)
    configure_tracing(resolved)
    resolved_engine = engine if engine is not None else build_engine(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        prepare_database(app.state.engine)
        yield
        app.state.engine.dispose()

    application = FastAPI(
        title="Orbe",
        version=__version__,
        description="Mesa de leitura de dossiês com citações verificáveis.",
        lifespan=lifespan,
    )
    application.state.engine = resolved_engine
    application.state.settings = resolved
    # Caps how many uploads index at once so a burst of large files cannot exhaust
    # the worker threadpool and starve health checks and questions.
    application.state.index_semaphore = asyncio.Semaphore(resolved.index_max_concurrency)
    if indexer is None or reader is None:
        history = SqlReadingHistory(resolved_engine)
        embeddings = OpenAIEmbeddingAdapter(resolved)
        store = PgExcerptStore(resolved, embeddings, resolved_engine)

        def require_key() -> None:
            require_openai_key(resolved)

        indexer = DossierIndexer(store, history, require_key, resolved)
        reader = DossierReader(store, OpenAIAnswerChain(resolved), history, require_key, resolved)
        application.state.history = history
    application.state.indexer = indexer
    application.state.reader = reader

    @application.middleware("http")
    async def assign_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "").strip()
        request_id = incoming[:128] if incoming else uuid.uuid4().hex
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log_request(request.method, request.url.path, response.status_code)
        return response

    application.include_router(router)
    application.include_router(page_router)
    register_error_handlers(application)
    return application
