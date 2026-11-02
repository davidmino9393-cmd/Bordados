import { useState, type ChangeEvent } from 'react';
import { useApi } from '../../api/ApiProvider';
import type { SourceAsset } from '../../contracts/project';
import type { UploadLimits } from '../../contracts/settings';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { formatMegabytes } from '../../shared/utils/format';
import { AssetKindNotice } from './AssetKindNotice';
import { newIdempotencyKey } from '../../shared/utils/idempotency';

interface UploadPanelProps {
  projectId: string;
  limits: UploadLimits;
  assets: SourceAsset[];
  selected: SourceAsset | undefined;
  onSelect: (assetId: string) => void;
  onUploaded: (asset: SourceAsset) => void;
}

const typeNames = (mimeTypes: string[]) =>
  mimeTypes.map((m) => m.replace('image/', '').replace('svg+xml', 'svg').toUpperCase()).join(', ');

export function UploadPanel({ projectId, limits, assets, selected, onSelect, onUploaded }: UploadPanelProps) {
  const api = useApi();
  const [error, setError] = useState<string>();
  const [uploading, setUploading] = useState(false);
  const maxMb = formatMegabytes(limits.max_bytes);

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(undefined);
    // Validación local solo como ayuda: la autoridad es el backend.
    if (!(limits.accepted_mime_types as string[]).includes(file.type)) return setError(es.upload.wrongType);
    if (file.size > limits.max_bytes) return setError(es.upload.tooBig(maxMb));
    setUploading(true);
    try {
      onUploaded(await api.uploadAsset(projectId, file, newIdempotencyKey()));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  const originalUrl = selected?.original_download?.url;
  return (
    <Card>
      <Card.Header>{es.upload.title}</Card.Header>
      <Card.Body>
        <Field label={es.upload.choose} hint={es.upload.hint(typeNames(limits.accepted_mime_types), maxMb)}>
          <input type="file" accept={limits.accepted_mime_types.join(',')} onChange={handleFile} disabled={uploading} />
        </Field>
        {uploading && <p role="status">{es.upload.uploading}</p>}
        {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
        {assets.length > 1 && (
          <Field label={es.upload.pickAsset}>
            <select value={selected?.asset_id ?? ''} onChange={(e) => onSelect(e.target.value)}>
              {assets.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>{a.original_filename}</option>
              ))}
            </select>
          </Field>
        )}
        {selected && <AssetKindNotice asset={selected} />}
        {selected ? (
          <figure className="region-view">
            {originalUrl ? (
              <img src={originalUrl} alt={`Imagen original: ${selected.original_filename}`} />
            ) : (
              <p className="field__hint">{es.upload.unavailable}</p>
            )}
            <figcaption className="field__hint">
              {selected.original_filename} ·{' '}
              {selected.original_width_px && selected.original_height_px
                ? es.upload.pixels(selected.original_width_px, selected.original_height_px)
                : es.upload.pixelsUnknown}
            </figcaption>
          </figure>
        ) : (
          <p>{es.upload.none}</p>
        )}
      </Card.Body>
    </Card>
  );
}
