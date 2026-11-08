from uuid import UUID


class ServiceError(Exception):
    def __init__(
        self, code: str, message: str, status_code: int = 422, document_id: UUID | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.document_id = document_id
