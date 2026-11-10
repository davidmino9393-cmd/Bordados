import { useState } from 'react';
import { ArtifactKind, type Artifact } from '../../contracts/artifacts';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';

interface ComparePanelProps {
  asset: SourceAsset | undefined;
  artifacts: Artifact[];
}

/** Las imágenes se muestran con <img>: un SVG subido nunca se inyecta como HTML. */
export function ComparePanel({ asset, artifacts }: ComparePanelProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const ratio = asset?.original_width_px && asset.original_height_px ? asset.original_width_px / asset.original_height_px : undefined;
  const editable = artifacts.find((a) => a.kind === ArtifactKind.EditableSvg);
  const machineSvg = artifacts.find((a) => a.kind === ArtifactKind.InkStitchSvg);
  const duplicateMachineFile = asset?.media_type !== 'image/svg+xml' && editable?.sha256 === machineSvg?.sha256;
  const vector = duplicateMachineFile ? undefined : editable;
  // Solo vale como «relectura» la vista previa derivada del JEF releído.
  const preview = artifacts.find((a) => a.kind === ArtifactKind.PreviewPng && a.derived_from === 'jef_reread');
  // Sin JEF releído no hay vista previa de puntadas: no se reserva un hueco vacío para ella.
  const hasJef = artifacts.some((a) => a.kind === ArtifactKind.Jef);
  const items = [
    { label: es.result.original, src: asset?.original_download?.url },
    { label: es.result.vector, src: vector?.download?.url },
    ...(hasJef ? [{ label: es.result.jefPreview, src: preview?.download?.url }] : []),
  ];
  return (
    <Card>
      <Card.Header>{es.result.compareTitle}</Card.Header>
      <Card.Body>
        <div className="compare">
          {items.map(({ label, src }) => (
            <figure key={label} className={expanded === label ? 'compare__expanded' : undefined}>
              {src ? (
                <button
                  type="button"
                  className="compare__zoom"
                  aria-label={`${expanded === label ? 'Reducir' : 'Ampliar'} ${label}`}
                  aria-pressed={expanded === label}
                  onClick={() => setExpanded(expanded === label ? null : label)}
                >
                  <img
                    src={src}
                    alt={label}
                    style={{ aspectRatio: ratio, objectFit: label === es.result.vector && ratio ? 'cover' : 'contain' }}
                  />
                </button>
              ) : <p className="field__hint">Vista no disponible</p>}
              <figcaption>{label}</figcaption>
            </figure>
          ))}
        </div>
      </Card.Body>
    </Card>
  );
}
