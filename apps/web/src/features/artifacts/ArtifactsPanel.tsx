import type { Artifact } from '../../contracts/artifacts';
import { artifactKindLabel, es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { formatBytes, shortHash } from '../../shared/utils/format';

interface ArtifactsPanelProps {
  artifacts: Artifact[];
  hadMismatch: boolean;
}

export function ArtifactsPanel({ artifacts, hadMismatch }: ArtifactsPanelProps) {
  return (
    <Card>
      <Card.Header>{es.result.downloadsTitle}</Card.Header>
      <Card.Body>
        {hadMismatch && <Notice tone={NoticeTone.Warning}>{es.result.mismatch}</Notice>}
        <ul className="list">
          {artifacts.map((a) => (
            <li key={a.kind} className="list__item">
              <span>
                <strong>{artifactKindLabel[a.kind]}</strong>
                <span className="field__hint">
                  {' '}· {a.filename} · {formatBytes(a.size_bytes)} · {shortHash(a.sha256)}
                </span>
              </span>
              <a className="button secondary" href={a.download_url} download={a.filename}>
                Descargar<span className="visually-hidden"> {artifactKindLabel[a.kind]}</span>
              </a>
            </li>
          ))}
        </ul>
      </Card.Body>
    </Card>
  );
}
