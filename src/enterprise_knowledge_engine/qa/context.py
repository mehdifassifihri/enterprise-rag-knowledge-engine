import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.retrieval.schemas import SearchResult


class ContextSource(BaseModel):
    source_id: str
    document_id: UUID
    chunk_id: UUID
    filename: str | None
    page: int | None
    chunk_position: int
    start_offset: int | None
    end_offset: int | None
    content: str
    truncated: bool


def serialize_sources(sources: list[ContextSource]) -> str:
    return json.dumps(
        [s.model_dump(mode="json") for s in sources], ensure_ascii=False, separators=(",", ":")
    )


@dataclass(frozen=True)
class ContextBundle:
    sources: list[ContextSource]
    serialized: str


def qualifies(result: SearchResult, config: Settings) -> bool:
    # RRF and reranker values are not calibrated relevance thresholds.
    lexical = (
        result.keyword_rank is not None
        and result.keyword_score is not None
        and result.keyword_score > config.qa_min_keyword_score
    )
    semantic = (
        result.vector_rank is not None
        and result.cosine_similarity is not None
        and result.cosine_similarity >= config.qa_min_cosine_similarity
    )
    return lexical or semantic


def clip_source(result: SearchResult, source_id: str, length: int) -> ContextSource:
    content = result.content[:length].rstrip()
    end = result.end_offset
    if result.start_offset is not None and end is not None:
        end = min(end, result.start_offset + len(content))
    return ContextSource(
        source_id=source_id,
        document_id=result.document_id,
        chunk_id=result.chunk_id,
        filename=result.filename,
        page=result.page,
        chunk_position=result.chunk_position,
        start_offset=result.start_offset,
        end_offset=end,
        content=content,
        truncated=len(content) < len(result.content),
    )


def build_context(results: list[SearchResult], config: Settings) -> ContextBundle:
    sources: list[ContextSource] = []
    seen: set[UUID] = set()
    for result in results:
        if len(sources) >= config.qa_max_sources:
            break
        if result.chunk_id in seen or not result.content.strip() or not qualifies(result, config):
            continue
        seen.add(result.chunk_id)
        upper = min(len(result.content), config.qa_max_passage_chars)

        low, high = 0, upper
        while low < high:
            middle = (low + high + 1) // 2
            if (
                len(
                    serialize_sources(
                        sources + [clip_source(result, f"S{len(sources) + 1}", middle)]
                    )
                )
                <= config.qa_context_char_budget
            ):
                low = middle
            else:
                high = middle - 1
        if low >= min(32, len(result.content.strip())):
            source = clip_source(result, f"S{len(sources) + 1}", low)
            if source.content:
                sources.append(source)
    return ContextBundle(sources=sources, serialized=serialize_sources(sources))
