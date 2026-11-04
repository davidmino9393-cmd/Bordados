import type { JobResponse } from '../../contracts/job';
import { ArtifactKind } from '../../contracts/artifacts';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { formatBytes } from '../../shared/utils/format';
import { guardArtifacts } from '../artifacts/artifactGuard';
import { useArtifactDownload } from '../artifacts/useArtifactDownload';
import { useArtifacts } from '../artifacts/useArtifacts';

interface JefHeroProps {
  job: JobResponse;
}

/** Lo que la persona vino a buscar: el JEF, arriba de todo, con el aviso de que sus parámetros no están calibrados. */
export function JefHero({ job }: JefHeroProps) {
  const { manifest, refresh } = useArtifacts(job.job_id);
  const { renewing, onDownload } = useArtifactDownload(refresh);
  const jef = manifest ? guardArtifacts(manifest, job.job_id).artifacts.find((a) => a.kind === ArtifactKind.Jef) : undefined;
  if (!jef) return null;
  return (
    <Card>
      <Card.Header>{es.review.jefHeroTitle}</Card.Header>
      <Card.Body>
        <p>{es.review.jefHeroText}</p>
        <div className="row">
          <a className="button" href={jef.download?.url} download={jef.filename} onClick={(e) => void onDownload(e, jef)}>
            {es.review.jefHeroDownload}
          </a>
          <span className="field__hint">{jef.filename} · {formatBytes(jef.byte_size)}</span>
        </div>
        {renewing && <p role="status">{es.result.renewing}</p>}
      </Card.Body>
    </Card>
  );
}
