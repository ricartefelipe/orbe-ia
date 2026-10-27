"""HTTP bodies for the reading desk."""

from uuid import UUID

from pydantic import BaseModel


class DocumentBody(BaseModel):
    """A file accepted by the desk."""

    id: UUID
    filename: str
    chunk_count: int
    duplicate: bool


class DocumentSummary(BaseModel):
    """One indexed file, as listed on the desk."""

    id: UUID
    filename: str
    chunk_count: int


class QueryIn(BaseModel):
    """A question about the indexed dossier."""

    question: str


class CitationBody(BaseModel):
    """One retrieved excerpt shown with the answer."""

    filename: str
    position: int
    content: str
    distance: float


class AnswerBody(BaseModel):
    """A persisted answer and the excerpts that grounded it."""

    id: UUID
    question: str
    answer: str
    grounded: bool
    citations: list[CitationBody]
