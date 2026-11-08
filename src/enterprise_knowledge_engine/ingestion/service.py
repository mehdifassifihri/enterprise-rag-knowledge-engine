import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.core.telemetry import measured
from enterprise_knowledge_engine.db.models import Document, DocumentChunk, Tenant
from enterprise_knowledge_engine.ingestion.chunking import chunk_sections
from enterprise_knowledge_engine.ingestion.embeddings import EmbeddingProvider, validate_vectors
from enterprise_knowledge_engine.ingestion.errors import IngestionError
from enterprise_knowledge_engine.ingestion.extraction import ExtractedDocument


def find_document(session: Session, tenant_id: UUID, document_id: UUID) -> Document:
    doc = session.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.id == document_id)
    )
    if doc is None:
        raise IngestionError("document_not_found", "Document not found", 404)
    return doc


def ingest(
    session: Session,
    tenant_id: UUID,
    data: bytes,
    extracted: ExtractedDocument,
    config: Settings,
    provider: EmbeddingProvider,
    reprocess: bool = False,
) -> Document:
    digest = hashlib.sha256(data).hexdigest()
    # Tenant+hash transaction lock prevents concurrent duplicate embedding work.
    lock_key = int.from_bytes(
        hashlib.sha256(f"{tenant_id}:{digest}".encode()).digest()[:8], "big", signed=True
    )
    failure: IngestionError | None = None
    with session.begin():
        locked = session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key})
        if not locked:
            raise IngestionError("document_busy", "An upload of this document is in progress", 409)
        if session.get(Tenant, tenant_id) is None:
            raise IngestionError(
                "tenant_not_provisioned", "Authenticated tenant is not provisioned", 403
            )
        doc = session.scalar(
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.content_hash == digest)
            .with_for_update()
        )
        if doc is not None and doc.status != "failed" and not reprocess:
            raise IngestionError("duplicate_document", "This document already exists", 409, doc.id)
        if doc is None:
            doc = Document(tenant_id=tenant_id, title=extracted.filename, content_hash=digest)
            session.add(doc)
            session.flush()
        session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.tenant_id == tenant_id, DocumentChunk.document_id == doc.id
            )
        )
        doc.filename = extracted.filename
        doc.size_bytes = len(data)
        doc.media_type = extracted.media_type
        doc.page_count = extracted.page_count
        doc.extraction_metadata = {"empty_pages": list(extracted.empty_pages)}
        doc.status, doc.chunk_count, doc.error_code = "processing", 0, None
        doc.embedding_model, doc.embedding_dimensions, doc.processed_at = None, None, None
        session.flush()
        try:
            # Savepoint ensures a failed insert/batch never leaves partial chunks.
            with session.begin_nested():
                chunks = chunk_sections(
                    extracted.sections, config.chunk_size, config.chunk_overlap, config.max_chunks
                )
                with measured("embedding_generation_completed", tenant_id=str(tenant_id)):
                    vectors = provider.embed([chunk.content for chunk in chunks])
                validate_vectors(vectors, len(chunks), config.embedding_dimensions)
                if provider.dimensions != config.embedding_dimensions:
                    raise IngestionError(
                        "embedding_invalid_response", "Embedding dimensions mismatch", 502
                    )
                session.add_all(
                    [
                        DocumentChunk(
                            tenant_id=tenant_id,
                            document_id=doc.id,
                            content=chunk.content,
                            position=chunk.position,
                            page_number=chunk.page_number,
                            start_offset=chunk.start_offset,
                            end_offset=chunk.end_offset,
                            embedding=vector,
                        )
                        for chunk, vector in zip(chunks, vectors, strict=True)
                    ]
                )
                session.flush()
            doc.status, doc.chunk_count = "ready", len(chunks)
            doc.embedding_model, doc.embedding_dimensions = provider.model, provider.dimensions
            doc.processed_at = datetime.now(UTC)
        except IngestionError as error:
            doc.status, doc.chunk_count, doc.error_code = "failed", 0, error.code
            failure = IngestionError(error.code, error.message, error.status_code, doc.id)
        except Exception:
            # Persist only a safe code; never expose provider/driver messages or input text.
            doc.status, doc.chunk_count, doc.error_code = "failed", 0, "processing_failed"
            failure = IngestionError("processing_failed", "Document processing failed", 500, doc.id)
    if failure:
        raise failure
    session.refresh(doc)
    return doc
