"""Boundaries the reading desk needs from infrastructure."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from orbe.domain.models import AskedQuestion, Chunk, Citation, IndexedFile, StoredDossier


class ExcerptStore(Protocol):
    """Vector store of dossier excerpts."""

    def add(self, key: str, filename: str, chunks: Sequence[Chunk]) -> None:
        """Index excerpts that belong to one file.

        ``key`` is the content fingerprint. Re-adding the same key replaces the
        same rows, so an interrupted indexing can be retried without duplicates.
        """

    def search(self, question: str, limit: int) -> Sequence[tuple[Chunk, float]]:
        """Return excerpts with their cosine distance, closest first."""

    def remove(self, key: str, count: int) -> None:
        """Drop the excerpts a file wrote under ``key``. Absent rows are ignored."""


class ReadingHistory(Protocol):
    """Persistence of files, questions, answers, and citations."""

    def find_file(self, digest: str) -> IndexedFile | None:
        """Return the file already stored for this content hash."""

    def list_files(self) -> Sequence[StoredDossier]:
        """Return the indexed files, most recent first."""

    def get_file(self, file_id: UUID) -> StoredDossier | None:
        """Return the recorded file for this id, or None when it is unknown."""

    def delete_file(self, file_id: UUID) -> None:
        """Remove the file row. The answered questions keep their excerpt snapshots."""

    def save_file(self, filename: str, digest: str, chunk_count: int) -> IndexedFile:
        """Record a newly indexed file, or the existing row when the hash collides."""

    def save_question(
        self,
        question: str,
        answer: str,
        grounded: bool,
        citations: Sequence[Citation],
    ) -> AskedQuestion:
        """Persist one completed reading."""


class AnswerChain(Protocol):
    """Language chain that may only speak from the supplied excerpts."""

    def answer(self, question: str, chunks: Sequence[Chunk]) -> str:
        """Answer the question using the excerpts."""
