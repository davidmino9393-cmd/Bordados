import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../../api/ApiClient';
import { useApi } from '../../api/ApiProvider';
import type { AuthorizedArtifactManifest } from '../../contracts/artifacts';
import { ErrorCode } from '../../contracts/http';
import { es } from '../../copy/es';
import { errorMessage } from '../../shared/hooks/useAsync';
import { useRenewBeforeExpiry } from '../../shared/hooks/useRenewBeforeExpiry';
import { earliestDownload } from '../../shared/utils/expiry';

/** 409 ARTIFACTS_UNAVAILABLE aunque el job traiga manifiesto: se explica sin culpar al usuario. */
function artifactsErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === ErrorCode.ArtifactsUnavailable) {
    return `${es.result.filesUnavailable} ${es.errors.incident(error.code, error.requestId)}`;
  }
  return errorMessage(error);
}

/**
 * GET /jobs/{id}/artifacts emite URLs nuevas que vencen a los 300 s. Se renuevan
 * antes del vencimiento y nunca se conservan más allá de `expires_at`.
 */
export function useArtifacts(jobId: string) {
  const api = useApi();
  const [manifest, setManifest] = useState<AuthorizedArtifactManifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await api.getArtifacts(jobId);
      setManifest(next);
      setError(null);
      return next;
    } catch (e) {
      // Con 409 los enlaces anteriores ya no sirven: no se dejan a la vista.
      if (e instanceof ApiError && e.code === ErrorCode.ArtifactsUnavailable) setManifest(null);
      setError(artifactsErrorMessage(e));
      return null;
    }
  }, [api, jobId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useRenewBeforeExpiry(earliestDownload((manifest?.artifacts ?? []).map((a) => a.download)), refresh);
  return { manifest, error, refresh };
}
