from enterprise_knowledge_engine.core.errors import ServiceError


class IngestionError(ServiceError):
    """A safely reportable ingestion failure."""
