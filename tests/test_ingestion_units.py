import math
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.ingestion.chunking import chunk_sections
from enterprise_knowledge_engine.ingestion.embeddings import (
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
    validate_vectors,
)
from enterprise_knowledge_engine.ingestion.errors import IngestionError
from enterprise_knowledge_engine.ingestion.extraction import TextSection, extract, normalize_text


def pdf_bytes(text: str | None = None, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if text:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 200 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("test-only-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize(
    "filename,data,code",
    [
        ("bad.exe", b"hello", "unsupported_format"),
        ("a.txt", b"", "empty_file"),
        ("a.md", b" \n\t", "empty_text"),
        ("a.pdf", b"hello", "invalid_pdf"),
        ("a.pdf", b"%PDF-1.7 broken", "invalid_pdf"),
        ("a.txt", b"%PDF-1.7 fake", "content_mismatch"),
        ("a.md", b"PK\x03\x04abc", "content_mismatch"),
        ("a.txt", b"hello\x00", "binary_content"),
        ("a.txt", b"\xff\xfe", "invalid_encoding"),
        ("a.txt", b"...!!!", "empty_text"),
    ],
)
def test_invalid_extraction(settings, filename, data, code):
    with pytest.raises(IngestionError) as error:
        extract(data, filename, settings)
    assert error.value.code == code


def test_normalization_and_safe_filename(settings):
    doc = extract(
        b"\xef\xbb\xbf# Title\r\n\r\n Hello\t world \r\n\r\n\r\nNext.", "../../unsafe.md", settings
    )
    assert doc.filename == "unsafe.md"
    assert doc.sections[0].text == "# Title\n\nHello world\n\nNext."
    assert normalize_text("e\u0301") == "é"


def test_pdf_text_and_page(settings):
    doc = extract(pdf_bytes("Readable PDF text."), "a.pdf", settings)
    assert doc.page_count == 1
    assert doc.sections[0].page_number == 1
    assert doc.sections[0].text == "Readable PDF text."


@pytest.mark.parametrize(
    "data,code",
    [
        (pdf_bytes(), "no_extractable_text"),
        (pdf_bytes("Secret", encrypted=True), "encrypted_pdf"),
    ],
)
def test_unreadable_pdf(settings, data, code):
    with pytest.raises(IngestionError) as error:
        extract(data, "a.pdf", settings)
    assert error.value.code == code


def test_extraction_limits(settings):
    settings.max_upload_bytes = 3
    with pytest.raises(IngestionError, match="MAX_UPLOAD_BYTES"):
        extract(b"1234", "a.txt", settings)
    settings.max_upload_bytes = 10000
    settings.max_extracted_chars = 100
    with pytest.raises(IngestionError, match="MAX_EXTRACTED_CHARS"):
        extract(b"a" * 101, "a.txt", settings)


@pytest.mark.parametrize("size,overlap", [(0, 0), (10, -1), (10, 10), (10, 11)])
def test_invalid_chunking(size, overlap):
    with pytest.raises(ValueError):
        chunk_sections([TextSection("hello")], size, overlap)


def test_chunking_coverage_locations_and_order():
    text = "First paragraph. " * 10 + "\n\n" + "Second paragraph. " * 20
    chunks = chunk_sections([TextSection(text, 3)], 100, 20)
    covered = set()
    for position, chunk in enumerate(chunks):
        assert chunk.position == position
        assert chunk.page_number == 3
        assert 0 < len(chunk.content) <= 100
        assert chunk.content == text[chunk.start_offset : chunk.end_offset]
        covered.update(range(chunk.start_offset, chunk.end_offset))
    assert all(i in covered for i, char in enumerate(text) if not char.isspace())
    assert all(b.start_offset > a.start_offset for a, b in zip(chunks, chunks[1:], strict=False))


def test_chunking_hard_split_and_limits():
    chunks = chunk_sections([TextSection("x" * 250)], 100, 0)
    assert [len(c.content) for c in chunks] == [100, 100, 50]
    with pytest.raises(IngestionError, match="MAX_CHUNKS"):
        chunk_sections([TextSection("x" * 250)], 100, 99, max_chunks=2)


def test_fake_embeddings_are_deterministic():
    provider = FakeEmbeddingProvider()
    first = provider.embed(["same", "different"])
    assert first == provider.embed(["same", "different"])
    assert first[0] != first[1]
    assert len(first[0]) == 1536
    assert math.isclose(sum(x * x for x in first[0]), 1)


@pytest.mark.parametrize("vectors", [[], [[1.0]], [[float("nan")] * 1536]])
def test_invalid_embedding_vectors(vectors):
    with pytest.raises(IngestionError):
        validate_vectors(vectors, 1, 1536)


def test_openai_batching_and_order(settings, monkeypatch):
    settings.embedding_batch_size = 2
    client = MagicMock()
    client.embeddings.create.side_effect = [
        SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[2.0]),
                SimpleNamespace(index=0, embedding=[1.0]),
            ]
        ),
        SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[3.0])]),
    ]
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr("enterprise_knowledge_engine.ingestion.embeddings.OpenAI", constructor)
    # model_copy validates secrets at construction below, unlike assignment to a test fixture.
    from pydantic import SecretStr

    settings.openai_api_key = SecretStr("test-only-openai-key")
    result = OpenAIEmbeddingProvider(settings).embed(["one", "two", "three"])
    assert result == [[1.0], [2.0], [3.0]]
    assert client.embeddings.create.call_count == 2
    assert client.embeddings.create.call_args_list[0].kwargs["model"] == "text-embedding-3-small"
    assert client.embeddings.create.call_args_list[0].kwargs["dimensions"] == 1536
    client.close.assert_called_once()


def test_openai_failure_is_safe(settings, monkeypatch):
    from openai import OpenAIError
    from pydantic import SecretStr

    settings.openai_api_key = SecretStr("test-only-openai-key")
    client = MagicMock()
    client.embeddings.create.side_effect = OpenAIError("private-api-response")
    monkeypatch.setattr(
        "enterprise_knowledge_engine.ingestion.embeddings.OpenAI", lambda **kw: client
    )
    with pytest.raises(IngestionError) as error:
        OpenAIEmbeddingProvider(settings).embed(["text"])
    assert error.value.status_code == 502
    assert "private-api-response" not in str(error.value)
    client.close.assert_called_once()


@pytest.mark.parametrize(
    "overrides",
    [
        {"chunk_overlap": 1500},
        {"chunk_size": 0},
        {"embedding_dimensions": 768},
        {"tenant_api_keys": {uuid4(): "short"}},
    ],
)
def test_invalid_ingestion_config(settings, overrides):
    with pytest.raises(ValueError):
        Settings(**(settings.model_dump() | overrides), _env_file=None)


def test_pdf_timeout_is_rejected(settings, monkeypatch):
    import subprocess

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("parser", 1)

    monkeypatch.setattr("enterprise_knowledge_engine.ingestion.extraction.subprocess.run", timeout)
    with pytest.raises(IngestionError, match="resource limits"):
        extract(b"%PDF-1.7 valid-signature", "a.pdf", settings)


def test_pdf_page_limit(settings):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    settings.max_pdf_pages = 1
    with pytest.raises(IngestionError) as error:
        extract(output.getvalue(), "a.pdf", settings)
    assert error.value.code == "too_many_pages"


def test_embedding_batches_limit_total_input():
    from enterprise_knowledge_engine.ingestion.embeddings import embedding_batches

    texts = ["é" * 4000] * 64
    batches = list(embedding_batches(texts, 64))
    assert sum(len(batch) for batch in batches) == 64
    assert len(batches) == 3
    assert all(sum(len(text.encode()) for text in batch) <= 250000 for batch in batches)
    with pytest.raises(IngestionError):
        list(embedding_batches(["x" * 8001], 32))


def test_duplicate_tenant_keys_are_rejected(settings):
    from conftest import TEST_KEY

    with pytest.raises(ValueError, match="unique"):
        Settings(
            **(settings.model_dump() | {"tenant_api_keys": {uuid4(): TEST_KEY}}), _env_file=None
        )
