from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from enterprise_knowledge_engine.db.models import Document
from enterprise_knowledge_engine.documents.schemas import DocumentList, DocumentResponse


def read_documents(session: Session, tenant_id: UUID, limit: int, offset: int) -> DocumentList:
    docs = session.scalars(
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return DocumentList(
        items=[DocumentResponse.model_validate(doc) for doc in docs], limit=limit, offset=offset
    )
