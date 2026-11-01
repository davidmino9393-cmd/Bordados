import { ApiError, ApiErrorCode, type ApiClient } from './ApiClient';

const BLOCKED_MESSAGE =
  'El servicio real aún no está conectado: los contratos v0.1 no están congelados.';

function blocked(): never {
  throw new ApiError(ApiErrorCode.ContractsNotFrozen, BLOCKED_MESSAGE);
}

/**
 * Esqueleto del cliente real. NO se conecta hasta que el integrador confirme
 * que los contratos v0.1 concretos están congelados. Cada método falla a propósito.
 */
export const httpApiClient: ApiClient = {
  isSimulated: false,
  getProfiles: async () => blocked(),
  listProjects: async () => blocked(),
  createProject: async () => blocked(),
  getProject: async () => blocked(),
  uploadAsset: async () => blocked(),
  createJob: async () => blocked(),
  getJob: async () => blocked(),
  getArtifacts: async () => blocked(),
  cancelJob: async () => blocked(),
  createRevision: async () => blocked(),
};
