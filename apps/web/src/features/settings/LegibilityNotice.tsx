import { useEffect, useState } from 'react';
import { useApi } from '../../api/ApiProvider';
import type { LegibilityCheck } from '../../contracts/legibility';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';

const DEBOUNCE_MS = 600;

interface LegibilityNoticeProps {
  projectId: string;
  assetId: string;
  widthMm: number;
  heightMm: number;
  colorLimit: number;
  hoop?: { width_mm: number; height_mm: number };
}

type State = { phase: 'loading' } | { phase: 'ready'; check: LegibilityCheck } | { phase: 'failed' };

/**
 * Orden 3.2: antes de generar, avisa con números si el trazo queda demasiado fino al tamaño pedido. Nunca bloquea el envío:
 * si la medición falla, se dice y se sigue. Ofrece el tamaño mínimo (o dice que no entra en el bastidor) y, aparte, la opción
 * de recortar el margen blanco, aclarando que eso no arregla las letras finas.
 */
export function LegibilityNotice({ projectId, assetId, widthMm, heightMm, colorLimit, hoop }: LegibilityNoticeProps) {
  const api = useApi();
  const [state, setState] = useState<State>({ phase: 'loading' });
  const hoopWidth = hoop?.width_mm;
  const hoopHeight = hoop?.height_mm;

  useEffect(() => {
    if (!(widthMm > 0 && heightMm > 0 && colorLimit >= 1)) return;
    let current = true;
    setState({ phase: 'loading' });
    const timer = setTimeout(() => {
      api
        .getLegibility(projectId, assetId, {
          width_mm: widthMm,
          height_mm: heightMm,
          color_limit: colorLimit,
          hoop_width_mm: hoopWidth,
          hoop_height_mm: hoopHeight,
        })
        .then((check) => current && setState({ phase: 'ready', check }))
        .catch(() => current && setState({ phase: 'failed' }));
    }, DEBOUNCE_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [api, projectId, assetId, widthMm, heightMm, colorLimit, hoopWidth, hoopHeight]);

  if (!(widthMm > 0 && heightMm > 0)) return null;
  const text = es.legibility;
  if (state.phase === 'loading') return <p className="field__hint" role="status">{text.measuring}</p>;
  if (state.phase === 'failed') return <Notice tone={NoticeTone.Info}>{text.unavailable}</Notice>;
  const { check } = state;
  const margin = check.margin_option && (
    <Notice tone={NoticeTone.Info} title={text.marginTitle}>
      <p>{check.margin_option.message}</p>
    </Notice>
  );
  return (
    <>
      {check.warn && check.message ? (
        <Notice tone={NoticeTone.Warning} title={text.warnTitle}>
          <p>{check.message}</p>
          <p className="field__hint">{text.notBlocking}</p>
          <p className="field__hint">{text.method}: {text.methodText}</p>
        </Notice>
      ) : (
        !check.minimum_size.already_legible && (
          <Notice tone={NoticeTone.Info} title={text.infoTitle}>
            <p>{text.belowLimit(Math.round(check.thin_share_below_0_6_mm * 100))} {check.minimum_size.message}</p>
          </Notice>
        )
      )}
      {margin}
    </>
  );
}
