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
  const vector = artifacts.find((a) => a.kind === ArtifactKind.SvgEditable);
  const preview = artifacts.find((a) => a.kind === ArtifactKind.JefPreview);
  const items = [
    { label: es.result.original, src: asset?.original_url },
    { label: es.result.vector, src: vector?.download_url },
    { label: es.result.jefPreview, src: preview?.download_url },
  ];
  return (
    <Card>
      <Card.Header>{es.result.compareTitle}</Card.Header>
      <Card.Body>
        <div className="compare">
          {items.map(({ label, src }) => (
            <figure key={label}>
              {src ? <img src={src} alt={label} /> : <p className="field__hint">—</p>}
              <figcaption>{label}</figcaption>
            </figure>
          ))}
        </div>
      </Card.Body>
    </Card>
  );
}
