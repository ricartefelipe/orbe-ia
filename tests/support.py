"""Fakes and dossier fixtures."""

from collections.abc import Sequence
from io import BytesIO
from typing import Any, cast
from uuid import UUID, uuid4

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from orbe.config.settings import Settings
from orbe.domain.errors import ModelCallFailed
from orbe.domain.models import AskedQuestion, Chunk, Citation, IndexedFile, StoredDossier


def settings(**overrides: Any) -> Settings:
    payload: dict[str, Any] = {
        "database_url": "postgresql+psycopg://orbe:orbe@127.0.0.1:5432/orbe_test",
        "app_env": "test",
        "openai_api_key": "",
        "langsmith_api_key": "",
    }
    payload.update(overrides)
    return Settings(**payload)


class ScriptedStore:
    """In-memory excerpts."""

    def __init__(self) -> None:
        self.added: list[Chunk] = []
        self.matches: list[tuple[Chunk, float]] = []
        self.add_keys: list[str] = []
        self.removed: list[tuple[str, int]] = []

    def add(self, key: str, filename: str, chunks: Sequence[Chunk]) -> None:
        self.add_keys.append(key)
        self.added.extend(chunks)

    def search(self, question: str, limit: int) -> Sequence[tuple[Chunk, float]]:
        return self.matches[:limit]

    def remove(self, key: str, count: int) -> None:
        self.removed.append((key, count))


class MemoryHistory:
    """In-memory files and questions."""

    def __init__(self) -> None:
        self.files: dict[str, IndexedFile] = {}
        self.by_id: dict[UUID, StoredDossier] = {}
        self.questions: list[AskedQuestion] = []

    def find_file(self, digest: str) -> IndexedFile | None:
        return self.files.get(digest)

    def list_files(self) -> list[StoredDossier]:
        return list(reversed(self.by_id.values()))

    def get_file(self, file_id: UUID) -> StoredDossier | None:
        return self.by_id.get(file_id)

    def delete_file(self, file_id: UUID) -> None:
        record = self.by_id.pop(file_id, None)
        if record is not None:
            self.files.pop(record.content_sha256, None)

    def save_file(self, filename: str, digest: str, chunk_count: int) -> IndexedFile:
        file_id = uuid4()
        indexed = IndexedFile(
            id=file_id,
            filename=filename,
            chunk_count=chunk_count,
            duplicate=False,
        )
        self.files[digest] = indexed
        self.by_id[file_id] = StoredDossier(
            id=file_id,
            filename=filename,
            content_sha256=digest,
            chunk_count=chunk_count,
        )
        return indexed

    def save_question(
        self,
        question: str,
        answer: str,
        grounded: bool,
        citations: Sequence[Citation],
    ) -> AskedQuestion:
        asked = AskedQuestion(
            id=uuid4(),
            question=question,
            answer=answer,
            grounded=grounded,
            citations=tuple(citations),
        )
        self.questions.append(asked)
        return asked


class ScriptedChain:
    """Answer chain that records whether it was called."""

    def __init__(self, answer: str = "Resposta citada.") -> None:
        self.answer_text = answer
        self.calls = 0

    def answer(self, question: str, chunks: Sequence[Chunk]) -> str:
        self.calls += 1
        if self.answer_text.strip() == "":
            raise ModelCallFailed("O modelo devolveu uma resposta vazia.")
        return self.answer_text


def allow_key() -> None:
    """Key check used when the test supplies its own model."""


def pdf_with_text(text: str = "Hello PDF") -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=144)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    page[NameObject("/Resources")] = resources
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 24 Tf 72 100 Td ({text}) Tj ET".encode())
    page.replace_contents(cast(Any, stream))
    raw = BytesIO()
    writer.write(raw)
    return raw.getvalue()


def blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    raw = BytesIO()
    writer.write(raw)
    return raw.getvalue()


def encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    raw = BytesIO()
    writer.write(raw)
    return raw.getvalue()
