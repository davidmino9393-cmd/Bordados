"""HTTP documents only. Authentication, storage and handlers are not implemented."""
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import ContractModel, Identifier, NonEmpty, Versioned


class ErrorCode(StrEnum):
    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    ARTIFACTS_UNAVAILABLE = "ARTIFACTS_UNAVAILABLE"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    INVALID_REQUEST = "INVALID_REQUEST"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


ERROR_STATUS = {
    ErrorCode.MALFORMED_REQUEST: 400, ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403, ErrorCode.NOT_FOUND: 404,
    ErrorCode.IDEMPOTENCY_CONFLICT: 409, ErrorCode.REVISION_CONFLICT: 409,
    ErrorCode.ARTIFACTS_UNAVAILABLE: 409, ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: 415, ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.RATE_LIMITED: 429, ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
}


class FieldError(ContractModel):
    field: NonEmpty
    message: NonEmpty


class ProblemResponse(Versioned):
    type: Annotated[str, Field(pattern=r"^urn:embroidery:problem:[a-z][a-z0-9-]*$")]
    title: NonEmpty
    status: Annotated[int, Field(ge=400, le=599)]
    detail: NonEmpty
    instance: Annotated[str, Field(pattern=r"^/api/v1/")]
    code: ErrorCode
    request_id: Identifier
    errors: tuple[FieldError, ...] = ()

    @model_validator(mode="after")
    def code_and_status_agree(self):
        if self.status != ERROR_STATUS[self.code]:
            raise ValueError("HTTP status must match the documented error code")
        expected_type = "urn:embroidery:problem:" + self.code.lower().replace("_", "-")
        if self.type != expected_type:
            raise ValueError("Problem type must match the documented error code")
        return self


class AssetUpload(ContractModel):
    file: Annotated[bytes, Field(json_schema_extra={"format": "binary"})]


class CancelRequest(Versioned):
    """No status/approval may be supplied by the client."""
