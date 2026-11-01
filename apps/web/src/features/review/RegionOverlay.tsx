import type { SourceAsset } from '../../contracts/project';
import type { PixelRegion } from '../../contracts/validation';

const REGION_STROKE_PX = 4;

/** Marca regiones en coordenadas de píxel del original sobre la imagen (<img>, no SVG en línea). */
export function RegionOverlay({ asset, regions }: { asset: SourceAsset; regions: PixelRegion[] }) {
  return (
    <>
      <img src={asset.original_url} alt={`Imagen original: ${asset.original_filename}`} />
      <svg viewBox={`0 0 ${asset.width_px} ${asset.height_px}`} aria-hidden="true">
        {regions.map((r) => (
          <rect
            key={r.object_id}
            x={r.x}
            y={r.y}
            width={r.width}
            height={r.height}
            fill="rgba(160, 40, 40, 0.15)"
            stroke="#a02828"
            strokeWidth={REGION_STROKE_PX}
          />
        ))}
      </svg>
    </>
  );
}
