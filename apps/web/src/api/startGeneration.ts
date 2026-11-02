import type { JobResponse } from '../contracts/job';
import type { SourceAsset } from '../contracts/project';
import { MediaType, type JobSettings } from '../contracts/settings';
import { CONTRACT_SCHEMA_VERSION } from '../contracts/version';
import type { ApiClient } from './ApiClient';

export const INITIAL_REVISION_REASON = 'Ajustes iniciales';

export function inputKindFor(asset: SourceAsset) {
  return asset.media_type === MediaType.Svg ? 'prepared_svg' : 'raster_image';
}

/**
 * Flujo inicial (openapi.json → x-initial-flow, pasos 3 y 4): primero la revisión
 * inicial con `base_revision_id: null` y luego el trabajo que la referencia.
 * Las claves derivan de `baseKey`: reintentar con la misma no duplica ninguno.
 */
export async function startGeneration(
  api: ApiClient,
  asset: SourceAsset,
  settings: JobSettings,
  baseKey: string,
): Promise<JobResponse> {
  const revision = await api.createInitialRevision(
    asset.project_id,
    {
      schema_version: CONTRACT_SCHEMA_VERSION,
      base_revision_id: null,
      reason: INITIAL_REVISION_REASON,
      settings,
    },
    `${baseKey}:revision`,
  );
  return api.createJob(
    asset.project_id,
    {
      schema_version: CONTRACT_SCHEMA_VERSION,
      asset_id: asset.asset_id,
      revision_id: revision.revision_id,
      input_kind: inputKindFor(asset),
      settings,
    },
    `${baseKey}:job`,
  );
}
