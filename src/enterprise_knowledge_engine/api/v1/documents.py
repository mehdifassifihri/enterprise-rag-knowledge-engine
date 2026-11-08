from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy import func, select

from enterprise_knowledge_engine.core.security import TenantIdentity
from enterprise_knowledge_engine.db.models import Document, DocumentChunk
from enterprise_knowledge_engine.db.session import DatabaseSession
from enterprise_knowledge_engine.documents.schemas import (
    ChunkPage,
    ChunkPreview,
    DocumentList,
    DocumentResponse,
    DocumentStats,
)
from enterprise_knowledge_engine.documents.service import read_documents
from enterprise_knowledge_engine.ingestion.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
)
from enterprise_knowledge_engine.ingestion.errors import IngestionError
from enterprise_knowledge_engine.ingestion.extraction import extract
from enterprise_knowledge_engine.ingestion.service import find_document, ingest

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    request: Request,
    tenant_id: TenantIdentity,
    session: DatabaseSession,
    provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    file: Annotated[UploadFile, File()],
    reprocess: bool = False,
) -> DocumentResponse:
    config = request.app.state.settings
    try:
        data = file.file.read(config.max_upload_bytes + 1)
        extracted = extract(data, file.filename, config)
        doc = ingest(session, tenant_id, data, extracted, config, provider, reprocess)
        return DocumentResponse.model_validate(doc)
    finally:
        file.file.close()


@router.get("", response_model=DocumentList)
def list_documents(
    tenant_id: TenantIdentity,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> DocumentList:
    return read_documents(session, tenant_id, limit, offset)


@router.get("/stats", response_model=DocumentStats)
def document_stats(tenant_id: TenantIdentity, session: DatabaseSession) -> DocumentStats:
    # Count actual rows rather than summing potentially stale document metadata.
    documents = (
        session.scalar(
            select(func.count()).select_from(Document).where(Document.tenant_id == tenant_id)
        )
        or 0
    )
    ready = (
        session.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.tenant_id == tenant_id, Document.status == "ready")
        )
        or 0
    )
    failed = (
        session.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.tenant_id == tenant_id, Document.status == "failed")
        )
        or 0
    )
    chunks = (
        session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .join(
                Document,
                (Document.id == DocumentChunk.document_id)
                & (Document.tenant_id == DocumentChunk.tenant_id),
            )
            .where(DocumentChunk.tenant_id == tenant_id, Document.tenant_id == tenant_id)
        )
        or 0
    )
    return DocumentStats(documents=documents, ready=ready, failed=failed, chunks=chunks)


@router.get("/{document_id}/chunks", response_model=ChunkPage)
def document_chunks(
    document_id: UUID,
    tenant_id: TenantIdentity,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> ChunkPage:
    find_document(session, tenant_id, document_id)
    rows = session.execute(
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.position,
            func.substr(DocumentChunk.content, 1, 2000).label("content"),
            DocumentChunk.page_number,
            DocumentChunk.start_offset,
            DocumentChunk.end_offset,
            (func.length(DocumentChunk.content) > 2000).label("truncated"),
        )
        .where(DocumentChunk.tenant_id == tenant_id, DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.position, DocumentChunk.id)
        .limit(limit)
        .offset(offset)
    ).mappings()
    return ChunkPage(items=[ChunkPreview(**row) for row in rows], limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID, tenant_id: TenantIdentity, session: DatabaseSession
) -> DocumentResponse:
    return DocumentResponse.model_validate(find_document(session, tenant_id, document_id))


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID, tenant_id: TenantIdentity, session: DatabaseSession
) -> Response:
    # A row lock serializes deletion with a reprocess; database cascades remove all vectors.
    with session.begin():
        doc = session.scalar(
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.id == document_id)
            .with_for_update()
        )
        if doc is None:
            raise IngestionError("document_not_found", "Document not found", 404)
        session.delete(doc)
    return Response(status_code=204)
