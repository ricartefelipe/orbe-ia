"""Boundaries the reading desk needs from infrastructure."""

from collections.abc import Sequence
from typing import Protocol

from orbe.domain.models import AskedQuestion, Chunk, Citation, IndexedFile


class ExcerptStore(Protocol):
    """Vector store of dossier excerpts."""

    def add(self, filename: str, chunks: Sequence[Chunk]) -> None:
        """Index excerpts that belong to one file."""

    def search(self, question: str, limit: int) -> Sequence[tuple[Chunk, float]]:
        """Return excerpts with their cosine distance, closest first."""


class ReadingHistory(Protocol):
    """Persistence of files, questions, answers, and citations."""

    def find_file(self, digest: str) -> IndexedFile | None:
        """Return the file already stored for this content hash."""

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
