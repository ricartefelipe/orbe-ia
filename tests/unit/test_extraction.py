"""Text extraction."""

import pytest

from orbe.domain.errors import UnreadableDossier
from orbe.infrastructure.extraction import extract_text
from tests.support import blank_pdf, encrypted_pdf, pdf_with_text


def test_markdown_and_text_keep_their_content() -> None:
    assert extract_text("notas.md", b"# Titulo\n") == "# Titulo"
    assert extract_text("notas.markdown", b"linha\n") == "linha"
    assert extract_text("notas.TXT", b"linha\n") == "linha"


def test_invalid_text_is_rejected() -> None:
    with pytest.raises(UnreadableDossier, match="UTF-8"):
        extract_text("notas.txt", b"\xff")
    with pytest.raises(UnreadableDossier, match="não contém texto"):
        extract_text("notas.txt", b"   \n")


def test_pdf_text_is_extracted_and_unreadable_files_are_rejected() -> None:
    assert extract_text("notas.pdf", pdf_with_text()) == "Hello PDF"
    with pytest.raises(UnreadableDossier, match="senha"):
        extract_text("notas.pdf", encrypted_pdf())
    with pytest.raises(UnreadableDossier, match="Não há OCR"):
        extract_text("notas.pdf", blank_pdf())
    with pytest.raises(UnreadableDossier, match="não é um PDF"):
        extract_text("notas.pdf", b"not-a-pdf")
    with pytest.raises(UnreadableDossier, match="não pôde ser lido"):
        extract_text("notas.pdf", b"%PDF-1.4\nnot a real body")
