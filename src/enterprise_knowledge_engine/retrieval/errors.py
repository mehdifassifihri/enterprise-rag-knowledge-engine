from enterprise_knowledge_engine.core.errors import ServiceError


class RetrievalError(ServiceError):
    """A safely reportable retrieval failure."""
