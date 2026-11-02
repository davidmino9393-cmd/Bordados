import type { AnalysisRegion } from '../../contracts/analysis';
import { es } from '../../copy/es';

interface RegionListProps {
  regions: AnalysisRegion[];
  uncertainIds: ReadonlySet<string>;
  flaggedIds: ReadonlySet<string>;
  onToggle: (regionId: string) => void;
}

/** Lista accesible de lo que detectó la IA: rol, texto, colores y dudas de cada región. */
export function RegionList({ regions, uncertainIds, flaggedIds, onToggle }: RegionListProps) {
  const text = es.analysis;
  return (
    <ul className="list">
      {regions.map((region) => {
        const uncertain = uncertainIds.has(region.region_id) || region.uncertainties.length > 0;
        return (
          <li key={region.region_id} className="issue" data-region-id={region.region_id}>
            <strong>
              {region.visual_role} <span className="field__hint">({region.region_id})</span>{' '}
              {uncertain && <span className="badge badge--warn">{text.uncertain}</span>}
            </strong>
            <span>
              {text.detectedText}: {region.observed_text ?? text.noText}
            </span>
            <span className="row">
              {text.colors}:
              {region.suggested_colors.map((color) => (
                <span key={color} className="swatch-label">
                  <span className="swatch" style={{ background: color }} aria-hidden="true" /> {color}
                </span>
              ))}
            </span>
            {region.uncertainties.length > 0 && (
              <ul>
                {region.uncertainties.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            )}
            <label className="radio">
              <input
                type="checkbox"
                checked={flaggedIds.has(region.region_id)}
                onChange={() => onToggle(region.region_id)}
              />
              {text.flag(region.visual_role)}
            </label>
          </li>
        );
      })}
    </ul>
  );
}
