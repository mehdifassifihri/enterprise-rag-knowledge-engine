import json
from unittest.mock import MagicMock
from uuid import UUID

from enterprise_knowledge_engine.qa.providers import FakeLLMProvider
from enterprise_knowledge_engine.retrieval.schemas import SearchResponse, SearchResult

FACT = "Retail returns can be requested within 21 calendar days of delivery."


def result(number=1, content=FACT, cosine=0.8, keyword=0.1):
    return SearchResult(
        chunk_id=UUID(int=number),
        document_id=UUID(int=100 + number),
        filename=f"policy{number}.md",
        content=content,
        page=2,
        chunk_position=0,
        start_offset=10,
        end_offset=10 + len(content),
        rank=number,
        score=0.03,
        score_type="rrf",
        retrieval_score=0.03,
        sources=["vector", "keyword"],
        vector_rank=number,
        keyword_rank=number,
        vector_distance=1 - cosine,
        cosine_similarity=cosine,
        normalized_similarity=(1 + cosine) / 2,
        keyword_score=keyword,
        rrf_score=0.03,
        rerank_score=None,
    )


def retrieved(items=None):
    return SearchResponse(
        query="policy",
        mode="hybrid",
        results=items if items is not None else [result()],
        score_type="rrf",
        rrf_k=60,
        candidate_limit_per_source=50,
        vector_strategy="exact",
        reranking_status="not_requested",
        reranker_model=None,
        warnings=[],
    )


def answer_json(source="S1", quote=FACT, text=FACT):
    return json.dumps(
        {
            "status": "answered",
            "claims": [{"text": text, "evidence": [{"source_id": source, "quote": quote}]}],
            "reason": None,
        }
    )


def scripted_llm(content=None):
    llm = MagicMock()
    llm.generate.side_effect = FakeLLMProvider(
        content if content is not None else answer_json()
    ).generate
    return llm
