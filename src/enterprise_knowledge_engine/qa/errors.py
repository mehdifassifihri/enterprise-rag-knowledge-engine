from enterprise_knowledge_engine.core.errors import ServiceError


class QAError(ServiceError):
    """A safely reportable question-answering error."""
