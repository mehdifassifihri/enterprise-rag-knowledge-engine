import re

from enterprise_knowledge_engine.qa.context import ContextBundle
from enterprise_knowledge_engine.qa.errors import QAError
from enterprise_knowledge_engine.qa.schemas import Citation, GeneratedAnswer

_CITATION_MARKER = re.compile(r"\[s[^\]]*\]", re.IGNORECASE)


def _source_quote(quote: str, content: str) -> str | None:
    """Match literal words allowing layout whitespace; return the original source span."""
    if not quote:
        return None
    if quote in content:
        return quote
    # PDF line wraps often become spaces in generated quotes. No case folding,
    # punctuation changes, omitted words, or fuzzy matching are permitted.
    pattern = r"\s+".join(re.escape(part) for part in quote.split())
    match = re.search(pattern, content) if pattern else None
    return match.group(0) if match else None


def validate_and_render(
    output: GeneratedAnswer, context: ContextBundle
) -> tuple[str, list[Citation]]:
    allowed = {source.source_id: source for source in context.sources}
    quotes: dict[str, list[str]] = {}
    rendered: list[str] = []
    for claim in output.claims:
        if not claim.text.strip() or _CITATION_MARKER.search(claim.text):
            raise QAError("invalid_citation", "Answer citation validation failed", 502)
        source_ids: list[str] = []
        for evidence in claim.evidence:
            source = allowed.get(evidence.source_id)
            quote = evidence.quote.strip()
            quote = _source_quote(quote, source.content) if source is not None else None
            if quote is None:
                raise QAError("invalid_citation", "Answer citation validation failed", 502)
            if evidence.source_id not in source_ids:
                source_ids.append(evidence.source_id)
            existing = quotes.setdefault(evidence.source_id, [])
            if quote not in existing:
                existing.append(quote)
        markers = " ".join(f"[{source_id}]" for source_id in source_ids)
        rendered.append(f"{claim.text.strip()} {markers}")
    citations = []
    for source in context.sources:
        supporting = quotes.get(source.source_id)
        if supporting:
            citations.append(
                Citation(
                    source_id=source.source_id,
                    document_id=source.document_id,
                    chunk_id=source.chunk_id,
                    filename=source.filename,
                    page=source.page,
                    chunk_position=source.chunk_position,
                    start_offset=source.start_offset,
                    end_offset=source.end_offset,
                    excerpt=supporting[0],
                    supporting_quotes=supporting,
                )
            )
    return "\n\n".join(rendered), citations
