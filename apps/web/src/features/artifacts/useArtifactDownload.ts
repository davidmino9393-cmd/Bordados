import { useState, type MouseEvent } from 'react';
import type { Artifact, AuthorizedArtifactManifest } from '../../contracts/artifacts';
import { isExpired, renewMargin } from '../../shared/utils/expiry';

function startDownload(url: string, filename: string) {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/** Un enlace vencido (o por vencer) no se usa: se reconsulta el manifiesto y se descarga el enlace nuevo. */
export function useArtifactDownload(refresh: () => Promise<AuthorizedArtifactManifest | null>) {
  const [renewing, setRenewing] = useState(false);

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

  return { renewing, onDownload };
}
