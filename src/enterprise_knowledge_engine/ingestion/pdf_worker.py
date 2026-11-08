"""Isolated PDF parser. Receives bytes on stdin; emits bounded extracted text as JSON."""

import json
import sys
from io import BytesIO

from pypdf import PdfReader


def main() -> None:
    # Linux container hard limits also bound decompression bombs. macOS uses the parent timeout.
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    max_pages, max_chars = map(int, sys.argv[1:3])
    try:
        reader = PdfReader(BytesIO(sys.stdin.buffer.read()), strict=True)
        if reader.is_encrypted:
            payload = {"error": "encrypted_pdf", "message": "Encrypted PDFs are not supported"}
        elif len(reader.pages) > max_pages:
            payload = {"error": "too_many_pages", "message": "PDF exceeds MAX_PDF_PAGES"}
        else:
            pages = []
            count = 0
            for page in reader.pages:
                text = page.extract_text() or ""
                count += len(text)
                if count > max_chars:
                    raise ValueError("text limit")
                pages.append(text)
            payload = {"pages": pages, "page_count": len(pages)}
    except Exception:
        payload = {
            "error": "invalid_pdf",
            "message": "PDF is unreadable or exceeds extraction limits",
        }
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    main()
