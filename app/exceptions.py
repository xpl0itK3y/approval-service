class ApprovalServiceError(Exception):
    """Base class for errors translated into HTTP responses by routers."""

    code = "internal_error"
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(ApprovalServiceError):
    code = "not_found"
    status_code = 404


class ConflictError(ApprovalServiceError):
    code = "conflict"
    status_code = 409


class ValidationErrorApp(ApprovalServiceError):
    code = "validation_error"
    status_code = 422
