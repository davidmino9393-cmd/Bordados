import { useEffect, useRef } from 'react';
import { RENEW_MARGIN_MS, msUntil } from '../utils/expiry';

/**
 * Vuelve a pedir los datos poco antes de que venza un enlace temporal (300 s).
 * No guarda nada más allá de `expiresAt`: al renovarse llegan URLs nuevas.
 */
export function useRenewBeforeExpiry(expiresAt: string | undefined, renew: () => void) {
  const renewRef = useRef(renew);
  renewRef.current = renew;
  useEffect(() => {
    if (!expiresAt) return;
    const wait = Math.max(0, msUntil(expiresAt, Date.now()) - RENEW_MARGIN_MS);
    const timer = setTimeout(() => renewRef.current(), wait);
    return () => clearTimeout(timer);
  }, [expiresAt]);
}
