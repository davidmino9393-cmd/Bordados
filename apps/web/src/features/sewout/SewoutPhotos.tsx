import { useApi } from '../../api/ApiProvider';
import { es } from '../../copy/es';
import { useAsync } from '../../shared/hooks/useAsync';
import { useRenewBeforeExpiry } from '../../shared/hooks/useRenewBeforeExpiry';
import { earliestDownload } from '../../shared/utils/expiry';

interface SewoutPhotosProps {
  projectId: string;
  photoIds: string[];
}

/** Fotos de la muestra registrada: salen del proyecto (enlaces de 300 s, que se renuevan solos). */
export function SewoutPhotos({ projectId, photoIds }: SewoutPhotosProps) {
  const api = useApi();
  const project = useAsync(() => api.getProject(projectId), [api, projectId, photoIds.join(',')]);
  const photos = (project.data?.assets ?? []).filter((asset) => photoIds.includes(asset.asset_id));
  useRenewBeforeExpiry(earliestDownload(photos.map((p) => p.original_download)), project.reload);
  if (photos.length === 0) return null;
  return (
    <ul className="photo-list" aria-label={es.sewout.photosTitle}>
      {photos.map((photo) => (
        <li key={photo.asset_id}>
          {photo.original_download ? (
            <img src={photo.original_download.url} alt={`${es.sewout.photoAlt}: ${photo.original_filename}`} />
          ) : (
            <span className="field__hint">{photo.original_filename}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
