import type { AnalysisRegion } from '../../contracts/analysis';

const STROKE_PX = 3;

interface AnalysisOverlayProps {
  imageUrl: string | undefined;
  imageAlt: string;
  /** Tamaño del original en píxeles; si no se conoce, se deduce de las cajas. */
  size: { width: number; height: number };
  regions: AnalysisRegion[];
  uncertainIds: ReadonlySet<string>;
  flaggedIds: ReadonlySet<string>;
}

const strokeFor = (uncertain: boolean, flagged: boolean) =>
  flagged ? '#a02828' : uncertain ? '#8a5a00' : '#2f5d8a';

/**
 * Cajas estimadas por la IA sobre el original. Son una ayuda visual (aria-hidden): la información
 * accesible es la lista de regiones. Las inciertas van con trazo discontinuo; las marcadas, en rojo.
 */
export function AnalysisOverlay({ imageUrl, imageAlt, size, regions, uncertainIds, flaggedIds }: AnalysisOverlayProps) {
  return (
    <div className="region-view">
      {imageUrl && <img src={imageUrl} alt={imageAlt} />}
      <svg viewBox={`0 0 ${size.width} ${size.height}`} aria-hidden="true" focusable="false">
        {regions.map((region) => {
          const uncertain = uncertainIds.has(region.region_id);
          const flagged = flaggedIds.has(region.region_id);
          const { x_px, y_px, width_px, height_px } = region.bounds_px;
          return (
            <rect
              key={region.region_id}
              x={x_px}
              y={y_px}
              width={width_px}
              height={height_px}
              fill={flagged ? 'rgba(160, 40, 40, 0.12)' : 'none'}
              stroke={strokeFor(uncertain, flagged)}
              strokeWidth={flagged ? STROKE_PX * 2 : STROKE_PX}
              strokeDasharray={uncertain ? '12 8' : undefined}
              data-region-id={region.region_id}
            />
          );
        })}
      </svg>
    </div>
  );
}

/** Tamaño de lienzo: el del original o, si falta, el que abarcan las cajas. */
export function canvasSize(
  original: { width: number | null; height: number | null },
  regions: AnalysisRegion[],
): { width: number; height: number } {
  if (original.width && original.height) return { width: original.width, height: original.height };
  const right = Math.max(1, ...regions.map((r) => r.bounds_px.x_px + r.bounds_px.width_px));
  const bottom = Math.max(1, ...regions.map((r) => r.bounds_px.y_px + r.bounds_px.height_px));
  return { width: right, height: bottom };
}
