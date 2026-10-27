"""SQL history of dossier files, questions, and citations."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, delete, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from orbe.domain.models import AskedQuestion, Citation, IndexedFile, StoredDossier


class Base(DeclarativeBase):
    """SQLAlchemy registry for the desk tables."""


class DossierFileRow(Base):
    """One uploaded dossier file, unique by content hash."""

    __tablename__ = "dossier_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    chunk_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AskedQuestionRow(Base):
    """One question asked of the desk."""

    __tablename__ = "asked_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    grounded: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AskedCitationRow(Base):
    """One citation attached to a question. The text is the retrieved excerpt."""

    __tablename__ = "asked_citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asked_questions.id", ondelete="CASCADE"),
    )
    filename: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    distance: Mapped[float] = mapped_column(Float)


class SqlReadingHistory:
    """PostgreSQL persistence for files and readings."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_file(self, digest: str) -> IndexedFile | None:
        with Session(self._engine) as session:
            row = session.scalar(
                select(DossierFileRow).where(DossierFileRow.content_sha256 == digest)
            )
        if row is None:
            return None
        return IndexedFile(
            id=row.id,
            filename=row.filename,
            chunk_count=row.chunk_count,
            duplicate=False,
        )

    def list_files(self) -> list[StoredDossier]:
        with Session(self._engine) as session:
            rows = session.scalars(
                select(DossierFileRow).order_by(DossierFileRow.created_at.desc())
            ).all()
        return [
            StoredDossier(
                id=row.id,
                filename=row.filename,
                content_sha256=row.content_sha256,
                chunk_count=row.chunk_count,
            )
            for row in rows
        ]

    def get_file(self, file_id: uuid.UUID) -> StoredDossier | None:
        with Session(self._engine) as session:
            row = session.get(DossierFileRow, file_id)
            if row is None:
                return None
            return StoredDossier(
                id=row.id,
                filename=row.filename,
                content_sha256=row.content_sha256,
                chunk_count=row.chunk_count,
            )

    def delete_file(self, file_id: uuid.UUID) -> None:
        with Session(self._engine) as session, session.begin():
            session.execute(delete(DossierFileRow).where(DossierFileRow.id == file_id))

    def save_file(self, filename: str, digest: str, chunk_count: int) -> IndexedFile:
        file_id = uuid.uuid4()
        try:
            with Session(self._engine) as session, session.begin():
                session.add(
                    DossierFileRow(
                        id=file_id,
                        filename=filename,
                        content_sha256=digest,
                        chunk_count=chunk_count,
                        created_at=datetime.now(UTC),
                    )
                )
        except IntegrityError:
            existing = self.find_file(digest)
            if existing is None:
                raise
            return IndexedFile(
                id=existing.id,
                filename=existing.filename,
                chunk_count=existing.chunk_count,
                duplicate=True,
            )
        return IndexedFile(
            id=file_id,
            filename=filename,
            chunk_count=chunk_count,
            duplicate=False,
        )

    def save_question(
        self,
        question: str,
        answer: str,
        grounded: bool,
        citations: Sequence[Citation],
    ) -> AskedQuestion:
        question_id = uuid.uuid4()
        saved = tuple(citations)
        with Session(self._engine) as session, session.begin():
            session.add(
                AskedQuestionRow(
                    id=question_id,
                    question=question,
                    answer=answer,
                    grounded=grounded,
                    created_at=datetime.now(UTC),
                )
            )
            session.flush()
            for citation in saved:
                session.add(
                    AskedCitationRow(
                        id=uuid.uuid4(),
                        question_id=question_id,
                        filename=citation.filename,
                        position=citation.position,
                        content=citation.content,
                        distance=citation.distance,
                    )
                )
        return AskedQuestion(
            id=question_id,
            question=question,
            answer=answer,
            grounded=grounded,
            citations=saved,
        )
