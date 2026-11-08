import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.ingestion.errors import IngestionError


@dataclass(frozen=True)
class TextSection:
    text: str
    page_number: int | None = None


@dataclass(frozen=True)
class ExtractedDocument:
    filename: str
    media_type: str
    sections: list[TextSection]
    page_count: int | None = None
    empty_pages: tuple[int, ...] = ()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def validate_filename(filename: str | None) -> tuple[str, str]:
    # Metadata only: never use a client filename as a filesystem path.
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    if not name or len(name) > 255 or any(unicodedata.category(c).startswith("C") for c in name):
        raise IngestionError("invalid_filename", "A filename of at most 255 characters is required")
    extension = PurePosixPath(name).suffix.lower()
    if extension not in {".pdf", ".txt", ".md", ".markdown"}:
        raise IngestionError(
            "unsupported_format", "Supported extensions: .pdf, .txt, .md, .markdown", 415
        )
    return name, extension


def extract(data: bytes, filename: str | None, config: Settings) -> ExtractedDocument:
    name, extension = validate_filename(filename)
    if not data:
        raise IngestionError("empty_file", "The uploaded file is empty")
    if len(data) > config.max_upload_bytes:
        raise IngestionError("file_too_large", "The uploaded file exceeds MAX_UPLOAD_BYTES", 413)
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise IngestionError("invalid_pdf", "The file does not contain a PDF signature")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "enterprise_knowledge_engine.ingestion.pdf_worker",
                    str(config.max_pdf_pages),
                    str(config.max_extracted_chars),
                ],
                env={"PATH": os.defpath, "PYTHONIOENCODING": "utf-8"},
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=config.pdf_timeout_seconds,
                check=True,
            )
            payload = json.loads(result.stdout)
        except (subprocess.SubprocessError, ValueError, OSError):
            raise IngestionError(
                "invalid_pdf", "PDF parsing failed or exceeded resource limits"
            ) from None
        if "error" in payload:
            raise IngestionError(payload["error"], payload["message"])
        sections = [TextSection(normalize_text(t), i + 1) for i, t in enumerate(payload["pages"])]
        empty_pages = tuple(s.page_number for s in sections if not s.text)
        sections = [s for s in sections if s.text]
        if not sections or not any(c.isalnum() for s in sections for c in s.text):
            raise IngestionError(
                "no_extractable_text", "PDF has no readable text; OCR is not supported"
            )
        return ExtractedDocument(
            name, "application/pdf", sections, payload["page_count"], empty_pages
        )
    if data.startswith((b"%PDF-", b"PK\x03\x04", b"\x89PNG", b"\xff\xd8\xff")):
        raise IngestionError(
            "content_mismatch", "The file content does not match a text document", 415
        )
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise IngestionError("invalid_encoding", "Text files must be valid UTF-8") from None
    if any(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in text):
        raise IngestionError(
            "binary_content", "Binary or control characters are not supported", 415
        )
    if len(text) > config.max_extracted_chars:
        raise IngestionError("text_too_large", "Extracted text exceeds MAX_EXTRACTED_CHARS")
    normalized = normalize_text(text)
    if not normalized or not any(c.isalnum() for c in normalized):
        raise IngestionError("empty_text", "The document has no readable text")
    media_type = "text/plain" if extension == ".txt" else "text/markdown"
    return ExtractedDocument(name, media_type, [TextSection(normalized)])
