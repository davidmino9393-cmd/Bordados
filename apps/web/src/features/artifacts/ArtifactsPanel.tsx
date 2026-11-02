import { useState, type MouseEvent } from 'react';
import { ArtifactKind, type Artifact, type AuthorizedArtifactManifest } from '../../contracts/artifacts';
import { artifactKindLabel, es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { isExpired, renewMargin } from '../../shared/utils/expiry';
import { formatBytes, shortHash } from '../../shared/utils/format';

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

function startDownload(url: string, filename: string) {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function ArtifactsPanel({ artifacts, hadMismatch, refresh }: ArtifactsPanelProps) {
  const [renewing, setRenewing] = useState(false);

  // Un enlace vencido (o por vencer) no se usa: se reconsulta y se descarga el nuevo.
  const onDownload = async (event: MouseEvent, artifact: Artifact) => {
    const download = artifact.download;
    if (download && !isExpired(download.expires_at, Date.now(), renewMargin(download))) return;
    event.preventDefault();
    setRenewing(true);
    const fresh = await refresh();
    setRenewing(false);
    const next = fresh?.artifacts.find((a) => a.artifact_id === artifact.artifact_id);
    if (next?.download) startDownload(next.download.url, next.filename);
  };

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
