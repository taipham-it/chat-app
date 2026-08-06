class AppError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication required.", *, code: str = "AUTH_REQUIRED"):
        super().__init__(message, code=code, status_code=401)


class AuthorizationError(AppError):
    def __init__(self, message: str = "You are not allowed to do that.", *, code: str = "ACCESS_DENIED"):
        super().__init__(message, code=code, status_code=403)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.", *, code: str = "NOT_FOUND"):
        super().__init__(message, code=code, status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str, *, code: str = "CONFLICT"):
        super().__init__(message, code=code, status_code=409)


class ValidationError(AppError):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR"):
        super().__init__(message, code=code, status_code=422)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str, *, code: str = "SERVICE_UNAVAILABLE"):
        super().__init__(message, code=code, status_code=503)
