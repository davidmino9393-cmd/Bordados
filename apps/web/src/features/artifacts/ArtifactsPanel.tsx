import { ArtifactKind, type Artifact, type AuthorizedArtifactManifest } from '../../contracts/artifacts';
import { artifactKindLabel, es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { formatBytes, shortHash } from '../../shared/utils/format';
import { useArtifactDownload } from './useArtifactDownload';

const TECHNICAL_KINDS: ArtifactKind[] = [
  ArtifactKind.StitchPlanJson,
  ArtifactKind.RawCommandsJson,
  ArtifactKind.ProviderRawJson,
];

interface ArtifactsPanelProps {
  artifacts: Artifact[];
  hadMismatch: boolean;
  /** Vuelve a pedir GET artifacts (URLs nuevas). */
  refresh: () => Promise<AuthorizedArtifactManifest | null>;
}

export function ArtifactsPanel({ artifacts, hadMismatch, refresh }: ArtifactsPanelProps) {
  const { renewing, onDownload } = useArtifactDownload(refresh);

  const row = (a: Artifact) => (
    <li key={a.artifact_id} className="list__item">
      <span>
        <strong>{artifactKindLabel[a.kind]}</strong>
        <span className="field__hint"> · {a.filename} · {formatBytes(a.byte_size)} · {shortHash(a.sha256)}</span>
      </span>
      <a
        className="button secondary"
        href={a.download?.url}
        download={a.filename}
        onClick={(e) => void onDownload(e, a)}
      >
        {es.result.download}{' '}
        <span className="visually-hidden">{artifactKindLabel[a.kind]}</span>
      </a>
    </li>
  );

  const technical = artifacts.filter((a) => TECHNICAL_KINDS.includes(a.kind));
  return (
    <Card>
      <Card.Header>{es.result.downloadsTitle}</Card.Header>
      <Card.Body>
        {hadMismatch && <Notice tone={NoticeTone.Warning}>{es.result.mismatch}</Notice>}
        {renewing && <p role="status">{es.result.renewing}</p>}
        <ul className="list">{artifacts.filter((a) => !TECHNICAL_KINDS.includes(a.kind)).map(row)}</ul>
        {technical.length > 0 && (
          <details>
            <summary>{es.result.technicalFiles}</summary>
            <ul className="list">{technical.map(row)}</ul>
          </details>
        )}
        <p className="field__hint">{es.result.linkNote}</p>
      </Card.Body>
    </Card>
  );
}
