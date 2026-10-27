"""Values exchanged by the reading desk."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Chunk:
    """A retrieved or indexed excerpt of a dossier file."""

    filename: str
    position: int
    content: str


@dataclass(frozen=True)
class Citation:
    """An excerpt that grounded an answer. The text comes from retrieval."""

    filename: str
    position: int
    content: str
    distance: float


@dataclass(frozen=True)
class IndexedFile:
    """A dossier file known to the desk."""

    id: UUID
    filename: str
    chunk_count: int
    duplicate: bool


@dataclass(frozen=True)
class StoredDossier:
    """A dossier file as recorded, with what deletion needs to find its excerpts."""

    id: UUID
    filename: str
    content_sha256: str
    chunk_count: int


@dataclass(frozen=True)
class AskedQuestion:
    """A persisted question together with the answer and its citations."""

    id: UUID
    question: str
    answer: str
    grounded: bool
    citations: tuple[Citation, ...]
