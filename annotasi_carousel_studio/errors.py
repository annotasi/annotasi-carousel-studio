from __future__ import annotations

from .common import *

class AppError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(HTTPStatus.BAD_GATEWAY, "ai_validation_failed", message)
