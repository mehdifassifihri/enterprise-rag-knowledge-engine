import re
from dataclasses import dataclass

from enterprise_knowledge_engine.ingestion.errors import IngestionError
from enterprise_knowledge_engine.ingestion.extraction import TextSection


@dataclass(frozen=True)
class Chunk:
    content: str
    position: int
    page_number: int | None
    start_offset: int
    end_offset: int


def chunk_sections(
    sections: list[TextSection], size: int, overlap: int, max_chunks: int = 1000
) -> list[Chunk]:
    if size < 1 or overlap < 0 or overlap >= size or max_chunks < 1:
        raise ValueError("Require size > overlap >= 0 and max_chunks > 0")
    chunks: list[Chunk] = []
    for section in sections:
        start = 0
        text = section.text
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                # Prefer paragraph, then sentence, then word boundaries in the latter half.
                window = text[start + size // 2 : end]
                for pattern in (r"\n\n", r"[.!?]\s+", r"\s+"):
                    matches = list(re.finditer(pattern, window))
                    if matches:
                        end = start + size // 2 + matches[-1].end()
                        break
            left, right = start, end
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                chunks.append(
                    Chunk(text[left:right], len(chunks), section.page_number, left, right)
                )
                if len(chunks) > max_chunks:
                    raise IngestionError("too_many_chunks", "Document exceeds MAX_CHUNKS")
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
    if not chunks:
        raise IngestionError("empty_text", "The document has no chunkable text")
    return chunks
