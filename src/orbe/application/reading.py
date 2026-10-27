"""Index a dossier and answer from the excerpts that were retrieved."""

import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path
from uuid import UUID

from langchain_text_splitters import RecursiveCharacterTextSplitter

from orbe.application.chain import UNGROUNDED_ANSWER
from orbe.application.ports import AnswerChain, ExcerptStore, ReadingHistory
from orbe.config.settings import Settings
from orbe.domain.errors import DossierNotFound, InvalidQuestion, UnreadableDossier
from orbe.domain.models import AskedQuestion, Chunk, Citation, IndexedFile, StoredDossier
from orbe.infrastructure.extraction import extract_text

_ALLOWED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}
_MAX_NAME_LENGTH = 255


def validate_upload(filename: str, content: bytes, max_bytes: int) -> str:
    """Accept a bare filename of a supported type, within the size limit."""

    if (
        filename == ""
        or filename in {".", ".."}
        or "\x00" in filename
        or "/" in filename
        or "\\" in filename
        or len(filename) > _MAX_NAME_LENGTH
    ):
        raise UnreadableDossier("O nome do arquivo é inválido.")
    bare = Path(filename).name
    if bare != filename:
        raise UnreadableDossier("O nome do arquivo é inválido.")
    if Path(bare).suffix.lower() not in _ALLOWED_SUFFIXES:
        raise UnreadableDossier("O tipo de arquivo não é aceito. Envie PDF, Markdown ou TXT.")
    if len(content) == 0:
        raise UnreadableDossier("O arquivo está vazio.")
    if len(content) > max_bytes:
        raise UnreadableDossier("O arquivo excede o tamanho permitido.")
    return bare


def validate_question(question: str, max_chars: int) -> str:
    """Strip the question and reject an empty or oversized one."""

    cleaned = question.strip()
    if cleaned == "":
        raise InvalidQuestion("A pergunta está vazia.")
    if len(cleaned) > max_chars:
        raise InvalidQuestion("A pergunta excede o tamanho permitido.")
    return cleaned


def split_excerpts(filename: str, text: str, settings: Settings) -> list[Chunk]:
    """Split dossier text with the LangChain recursive splitter."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        add_start_index=True,
    )
    documents = splitter.create_documents([text], metadatas=[{"filename": filename}])
    return [
        Chunk(
            filename=filename,
            position=int(document.metadata.get("start_index", 0)),
            content=document.page_content,
        )
        for document in documents
        if document.page_content.strip() != ""
    ]


class DossierIndexer:
    """Validate, extract, and index a dossier file."""

    def __init__(
        self,
        store: ExcerptStore,
        history: ReadingHistory,
        require_key: Callable[[], None],
        settings: Settings,
    ) -> None:
        self._store = store
        self._history = history
        self._require_key = require_key
        self._settings = settings

    def index(self, filename: str, content: bytes) -> IndexedFile:
        bare = validate_upload(filename, content, self._settings.document_max_bytes)
        text = extract_text(bare, content)
        self._require_key()
        digest = hashlib.sha256(content).hexdigest()
        existing = self._history.find_file(digest)
        if existing is not None:
            return IndexedFile(
                id=existing.id,
                filename=existing.filename,
                chunk_count=existing.chunk_count,
                duplicate=True,
            )
        chunks = split_excerpts(bare, text, self._settings)
        if not chunks:
            raise UnreadableDossier("O arquivo não contém texto.")
        # Excerpts land before the history row. A crash between the two leaves the
        # file undiscovered by find_file, so the retry re-adds with the same keys
        # (idempotent) and only then records the row. The desk never reports a file
        # as ready while its excerpts are missing.
        self._store.add(digest, bare, chunks)
        return self._history.save_file(bare, digest, len(chunks))

    def list(self) -> Sequence[StoredDossier]:
        """List the indexed files, most recent first. No model key needed."""

        return self._history.list_files()

    def remove(self, file_id: UUID) -> None:
        """Delete a dossier file and its excerpts. Deletion needs no model key.

        Excerpts go first, then the row. A crash in between leaves the file still
        recorded, so the retry finds it and removes the (already gone) excerpts
        again before dropping the row. Past answers keep the excerpts they cited;
        those are snapshots, not live links into the deleted file.
        """

        record = self._history.get_file(file_id)
        if record is None:
            raise DossierNotFound("O documento não existe.")
        self._store.remove(record.content_sha256, record.chunk_count)
        self._history.delete_file(file_id)


class DossierReader:
    """Answer a question from close excerpts, or say the dossier does not cover it."""

    def __init__(
        self,
        store: ExcerptStore,
        chain: AnswerChain,
        history: ReadingHistory,
        require_key: Callable[[], None],
        settings: Settings,
    ) -> None:
        self._store = store
        self._chain = chain
        self._history = history
        self._require_key = require_key
        self._settings = settings

    def ask(self, question: str) -> AskedQuestion:
        cleaned = validate_question(question, self._settings.query_max_chars)
        self._require_key()
        matches = self._store.search(cleaned, self._settings.query_match_limit)
        kept = [
            (chunk, distance)
            for chunk, distance in matches
            if distance <= self._settings.query_max_distance
        ]
        if not kept:
            return self._history.save_question(
                question=cleaned,
                answer=UNGROUNDED_ANSWER,
                grounded=False,
                citations=[],
            )
        answer = self._chain.answer(cleaned, [chunk for chunk, _distance in kept])
        citations: Sequence[Citation] = [
            Citation(
                filename=chunk.filename,
                position=chunk.position,
                content=chunk.content,
                distance=distance,
            )
            for chunk, distance in kept
        ]
        return self._history.save_question(
            question=cleaned,
            answer=answer,
            grounded=True,
            citations=citations,
        )
