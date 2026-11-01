"""Controlled public errors; private process logs are never included."""
from embroidery_contracts import ErrorCode


class ApiProblem(Exception):
    def __init__(self, code: ErrorCode | str, detail: str):
        self.code = ErrorCode(code)
        self.detail = detail
        super().__init__(detail)
