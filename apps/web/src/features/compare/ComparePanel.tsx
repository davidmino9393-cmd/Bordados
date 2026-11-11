import { useState } from 'react';
import { ArtifactKind, type Artifact } from '../../contracts/artifacts';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';

interface ComparePanelProps {
  asset: SourceAsset | undefined;
  artifacts: Artifact[];
}

/**
 * Original, vector y bordado en cajas iguales; al tocar una vista se amplía debajo. El fondo cuadriculado deja ver un
 * vector claro o con zonas vacías. Las imágenes se muestran con <img>: un SVG subido nunca se inyecta como HTML.
 */
export function ComparePanel({ asset, artifacts }: ComparePanelProps) {
  const [zoomed, setZoomed] = useState<string>();
  const editable = artifacts.find((a) => a.kind === ArtifactKind.EditableSvg);
  const machineSvg = artifacts.find((a) => a.kind === ArtifactKind.InkStitchSvg);
  // En una entrada ráster, una exportación vieja podía etiquetar el SVG de puntadas como editable: no se muestra duplicado.
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
  const enlarged = items.find((item) => item.label === zoomed && item.src);
  return (
    <Card>
      <Card.Header>{es.result.compareTitle}</Card.Header>
      <Card.Body>
        <p className="field__hint">{es.result.compareHint}</p>
        <div className="compare">
          {items.map(({ label, src }) => (
            <figure key={label}>
              {src ? (
                <button
                  type="button"
                  className="compare__view"
                  aria-label={es.result.zoomIn(label)}
                  aria-pressed={zoomed === label}
                  onClick={() => setZoomed(zoomed === label ? undefined : label)}
                >
                  <img src={src} alt={label} />
                </button>
              ) : (
                <p className="field__hint">—</p>
              )}
              <figcaption>{label}</figcaption>
            </figure>
          ))}
        </div>
        {enlarged && (
          <figure className="compare__zoom">
            <img src={enlarged.src} alt={es.result.zoomIn(enlarged.label)} />
            <figcaption className="row">
              <span>{enlarged.label}</span>
              <button type="button" className="secondary" onClick={() => setZoomed(undefined)}>{es.result.zoomClose}</button>
            </figcaption>
          </figure>
        )}
      </Card.Body>
    </Card>
  );
}
