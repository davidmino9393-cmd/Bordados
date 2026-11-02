// Contrato v0.1 — http.py (errores application/problem+json).

export const ErrorCode = {
  MalformedRequest: 'MALFORMED_REQUEST',
  Unauthenticated: 'UNAUTHENTICATED',
  Forbidden: 'FORBIDDEN',
  NotFound: 'NOT_FOUND',
  IdempotencyConflict: 'IDEMPOTENCY_CONFLICT',
  RevisionConflict: 'REVISION_CONFLICT',
  ArtifactsUnavailable: 'ARTIFACTS_UNAVAILABLE',
  PayloadTooLarge: 'PAYLOAD_TOO_LARGE',
  UnsupportedMediaType: 'UNSUPPORTED_MEDIA_TYPE',
  InvalidRequest: 'INVALID_REQUEST',
  RateLimited: 'RATE_LIMITED',
  InternalError: 'INTERNAL_ERROR',
  ServiceUnavailable: 'SERVICE_UNAVAILABLE',
} as const;
export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];

export interface FieldError {
  field: string;
  message: string;
}

export interface ProblemResponse {
  schema_version: string;
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  code: ErrorCode;
  request_id: string;
  errors: FieldError[];
}
