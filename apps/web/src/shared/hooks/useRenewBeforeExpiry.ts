import { useEffect, useRef } from 'react';
import type { ArtifactDownload } from '../../contracts/artifacts';
import { MIN_RENEW_WAIT_MS, msUntil, renewMargin } from '../utils/expiry';

/**
 * Vuelve a pedir los datos poco antes de que venza un enlace temporal (300 s).
 * No guarda nada más allá de `expires_at`: al renovarse llegan URLs nuevas.
 */
export function useRenewBeforeExpiry(download: ArtifactDownload | undefined, renew: () => void) {
  const renewRef = useRef(renew);
  renewRef.current = renew;
  const expiresAt = download?.expires_at;
  const issuedAt = download?.issued_at;
  useEffect(() => {
    if (!expiresAt || !issuedAt) return;
    const margin = renewMargin({ url: '', issued_at: issuedAt, expires_at: expiresAt });
    const wait = Math.max(MIN_RENEW_WAIT_MS, msUntil(expiresAt, Date.now()) - margin);
    const timer = setTimeout(() => renewRef.current(), wait);
    return () => clearTimeout(timer);
  }, [expiresAt, issuedAt]);
}
