import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.core.errors import ServiceError
from enterprise_knowledge_engine.ingestion.embeddings import EmbeddingProvider
from enterprise_knowledge_engine.qa.citations import validate_and_render
from enterprise_knowledge_engine.qa.context import build_context
from enterprise_knowledge_engine.qa.errors import QAError
from enterprise_knowledge_engine.qa.prompts import build_messages
from enterprise_knowledge_engine.qa.providers import LLMProvider
from enterprise_knowledge_engine.qa.schemas import (
    AnswerError,
    AskRequest,
    AskResponse,
    GeneratedAnswer,
    QATimings,
    RetrievalSummary,
    TokenUsage,
)
from enterprise_knowledge_engine.retrieval.reranking import Reranker
from enterprise_knowledge_engine.retrieval.schemas import SearchRequest
from enterprise_knowledge_engine.retrieval.service import search

logger = logging.getLogger(__name__)
ABSTENTION_TEXT = (
    "I don't have enough consistent evidence in the available sources to answer this question."
)
ERROR_TEXT = "An answer could not be generated. Please try again later."


@dataclass(frozen=True)
class AskOutcome:
    response: AskResponse
    http_status: int = 200


def answer_question(
    session: Session,
    tenant_id: UUID,
    request: AskRequest,
    config: Settings,
    embeddings: EmbeddingProvider,
    reranker: Reranker,
    llm: LLMProvider,
    request_id: str | None = None,
) -> AskOutcome:
    mode = request.search_mode or config.qa_search_mode
    top_k = request.top_k if request.top_k is not None else config.qa_default_top_k
    use_reranker = request.rerank if request.rerank is not None else config.qa_rerank
    summary = RetrievalSummary(
        mode=mode,
        top_k=top_k,
        sources_retrieved=0,
        sources_supplied=0,
        sources_used=0,
        context_characters=0,
        reranking_status=None,
        warnings=[],
    )
    timings = QATimings()
    usage: TokenUsage | None = None
    model: str | None = None
    status = "error"
    category: str | None = None
    http_status = 200
    error = None
    reason = None
    answer = ABSTENTION_TEXT
    citations = []
    safe_extra = {"request_id": request_id, "tenant_id": str(tenant_id)}
    try:
        started = perf_counter()
        try:
            retrieved = search(
                session,
                tenant_id,
                SearchRequest(
                    query=request.question,
                    mode=mode,
                    top_k=top_k,
                    rerank=use_reranker,
                ),
                config,
                embeddings,
                reranker,
            )
        finally:
            timings.retrieval_ms = round((perf_counter() - started) * 1000, 2)
        summary.sources_retrieved = len(retrieved.results)
        summary.reranking_status = retrieved.reranking_status
        summary.warnings = list(retrieved.warnings)
        context = build_context(retrieved.results, config)
        summary.sources_supplied = len(context.sources)
        summary.context_characters = len(context.serialized)
        logger.info(
            "qa_retrieval_completed",
            extra={
                **safe_extra,
                "retrieval_duration_ms": timings.retrieval_ms,
                "sources_count": summary.sources_supplied,
            },
        )
        if not context.sources:
            status, reason = "insufficient_evidence", "no_relevant_sources"
        else:
            started = perf_counter()
            try:
                completion = llm.generate(build_messages(request, context))
            except ServiceError:
                raise
            except Exception:
                raise QAError("llm_request_failed", "Answer provider request failed", 502) from None
            finally:
                timings.model_ms = round((perf_counter() - started) * 1000, 2)
            model, usage = completion.model, completion.usage
            logger.info(
                "qa_model_completed",
                extra={
                    **safe_extra,
                    "model_duration_ms": timings.model_ms,
                    "llm_model": model,
                    "input_tokens": usage.input_tokens if usage else None,
                    "output_tokens": usage.output_tokens if usage else None,
                    "total_tokens": usage.total_tokens if usage else None,
                },
            )
            try:
                if len(completion.content) > 32768:
                    raise ValueError("Output limit exceeded")
                output = GeneratedAnswer.model_validate_json(completion.content)
            except (ValidationError, ValueError, TypeError):
                raise QAError(
                    "llm_invalid_output", "Answer provider returned invalid output", 502
                ) from None
            status, reason = output.status, output.reason
            if status == "answered":
                answer, citations = validate_and_render(output, context)
                summary.sources_used = len(citations)
    except ServiceError as failure:
        status, category, http_status = "error", failure.code, failure.status_code
        answer, citations, reason = ERROR_TEXT, [], None
        error = AnswerError(code=category, message=failure.message)
    except SQLAlchemyError:
        status, category, http_status = "error", "database_unavailable", 503
        answer, citations, reason = ERROR_TEXT, [], None
        error = AnswerError(code=category, message="Knowledge database operation failed")
    except Exception:
        status, category, http_status = "error", "qa_internal_error", 500
        answer, citations, reason = ERROR_TEXT, [], None
        error = AnswerError(code=category, message="Question answering failed")
    logger.info(
        "qa_request_completed",
        extra={
            **safe_extra,
            "answer_status": status,
            "error_category": category,
            "retrieval_duration_ms": timings.retrieval_ms,
            "model_duration_ms": timings.model_ms,
            "sources_count": summary.sources_supplied,
            "status_code": http_status,
        },
    )
    return AskOutcome(
        response=AskResponse(
            question=request.question,
            answer=answer,
            status=status,
            abstention_reason=reason,
            citations=citations,
            retrieval=summary,
            model=model,
            usage=usage,
            timings=timings,
            request_id=request_id,
            error=error,
        ),
        http_status=http_status,
    )
