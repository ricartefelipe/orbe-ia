"""Database readiness. The OpenAI key is not part of this check."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from orbe.infrastructure.history import Base


def prepare_database(engine: Engine) -> None:
    """Create the vector extension and the desk tables."""

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def database_ready(engine: Engine) -> bool:
    """Return whether PostgreSQL answers and the vector extension is installed."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            row = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).first()
    except Exception:
        return False
    return row is not None
