import { useCallback, useEffect, useState } from 'react';
import { useApi } from '../../api/ApiProvider';
import type { AuthorizedArtifactManifest } from '../../contracts/artifacts';
import { errorMessage } from '../../shared/hooks/useAsync';
import { useRenewBeforeExpiry } from '../../shared/hooks/useRenewBeforeExpiry';
import { earliestDownload } from '../../shared/utils/expiry';

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
      setError(errorMessage(e));
      return null;
    }
  }, [api, jobId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useRenewBeforeExpiry(earliestDownload((manifest?.artifacts ?? []).map((a) => a.download)), refresh);
  return { manifest, error, refresh };
}
