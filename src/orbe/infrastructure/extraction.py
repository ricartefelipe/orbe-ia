"""Read dossier text with LangChain loaders. There is no OCR."""

import tempfile
from io import BytesIO
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from orbe.domain.errors import UnreadableDossier


def extract_text(filename: str, content: bytes) -> str:
    """Return the text of a PDF, Markdown, or TXT file."""

    suffix = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"dossier{suffix}"
        path.write_bytes(content)
        if suffix == ".pdf":
            return _pdf_text(path, content)
        return _plain_text(path)


def _plain_text(path: Path) -> str:
    try:
        documents = TextLoader(str(path), encoding="utf-8").load()
    except UnicodeDecodeError:
        raise UnreadableDossier("O arquivo não está em UTF-8.") from None
    except RuntimeError as exc:
        if isinstance(exc.__cause__, UnicodeDecodeError):
            raise UnreadableDossier("O arquivo não está em UTF-8.") from None
        raise UnreadableDossier("O arquivo não pôde ser lido.") from None
    text = "\n".join(document.page_content for document in documents).strip()
    if text == "":
        raise UnreadableDossier("O arquivo não contém texto.")
    return text


def _pdf_text(path: Path, content: bytes) -> str:
    if not content.startswith(b"%PDF"):
        raise UnreadableDossier("O arquivo não é um PDF válido.")
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise UnreadableDossier("O PDF está protegido por senha.")
    except UnreadableDossier:
        raise
    except FileNotDecryptedError:
        raise UnreadableDossier("O PDF está protegido por senha.") from None
    except PdfReadError:
        raise UnreadableDossier("O PDF não pôde ser lido.") from None
    try:
        documents = PyPDFLoader(str(path)).load()
    except Exception:
        raise UnreadableDossier("O PDF não pôde ser lido.") from None
    text = "\n".join(document.page_content for document in documents).strip()
    if text == "":
        raise UnreadableDossier("O PDF não contém texto. Não há OCR nesta versão.")
    return text
