from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy import select

from enterprise_knowledge_engine.core.security import TenantIdentity
from enterprise_knowledge_engine.db.models import Document
from enterprise_knowledge_engine.db.session import DatabaseSession
from enterprise_knowledge_engine.documents.schemas import DocumentList, DocumentResponse
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
