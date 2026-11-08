import math
from dataclasses import dataclass, replace
from typing import Literal
from uuid import UUID

from enterprise_knowledge_engine.retrieval.schemas import ScoreType


@dataclass(frozen=True)
class Candidate:
    chunk_id: UUID
    document_id: UUID
    filename: str | None
    content: str
    page: int | None
    chunk_position: int
    start_offset: int | None
    end_offset: int | None
    vector_distance: float | None = None
    keyword_score: float | None = None


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Candidate
    score: float
    score_type: ScoreType
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rrf_score: float | None = None


def cosine_scores(distance: float) -> tuple[float, float]:
    if not math.isfinite(distance) or distance < -1e-6 or distance > 2 + 1e-6:
        raise ValueError("Invalid cosine distance")
    distance = min(2.0, max(0.0, distance))
    return 1 - distance, 1 - distance / 2


def rank_candidates(
    candidates: list[Candidate], source: Literal["vector", "keyword"]
) -> list[RankedCandidate]:
    if source not in {"vector", "keyword"}:
        raise ValueError("Unknown retrieval source")
    scored: list[tuple[Candidate, float, float]] = []
    for candidate in candidates:
        if source == "vector":
            if candidate.vector_distance is None:
                raise ValueError("Missing vector distance")
            score = cosine_scores(candidate.vector_distance)[1]
            sort_value = candidate.vector_distance
        else:
            score = candidate.keyword_score
            if score is None or not math.isfinite(score) or score < 0:
                raise ValueError("Invalid keyword score")
            sort_value = -score
        scored.append((candidate, score, sort_value))
    scored.sort(key=lambda item: (item[2], item[0].chunk_id))
    result: list[RankedCandidate] = []
    seen: set[UUID] = set()
    for candidate, score, _ in scored:
        if candidate.chunk_id in seen:
            continue
        seen.add(candidate.chunk_id)
        rank = len(result) + 1
        result.append(
            RankedCandidate(
                candidate=candidate,
                score=score,
                score_type="normalized_cosine" if source == "vector" else "keyword_rank",
                vector_rank=rank if source == "vector" else None,
                keyword_rank=rank if source == "keyword" else None,
            )
        )
    return result


def reciprocal_rank_fusion(
    vectors: list[RankedCandidate],
    keywords: list[RankedCandidate],
    k: int = 60,
) -> list[RankedCandidate]:
    if k < 1:
        raise ValueError("RRF k must be positive")
    combined: dict[UUID, RankedCandidate] = {}
    for source, items in (("vector", vectors), ("keyword", keywords)):
        seen: set[UUID] = set()
        for item in items:
            chunk_id = item.candidate.chunk_id
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            rank = len(seen)
            previous = combined.get(chunk_id)
            candidate = (
                item.candidate
                if previous is None
                else replace(
                    previous.candidate,
                    keyword_score=item.candidate.keyword_score,
                )
            )
            score = (previous.score if previous else 0) + 1 / (k + rank)
            combined[chunk_id] = RankedCandidate(
                candidate=candidate,
                score=score,
                score_type="rrf",
                rrf_score=score,
                vector_rank=rank
                if source == "vector"
                else (previous.vector_rank if previous else None),
                keyword_rank=rank if source == "keyword" else None,
            )
    return sorted(combined.values(), key=lambda item: (-item.score, item.candidate.chunk_id))
