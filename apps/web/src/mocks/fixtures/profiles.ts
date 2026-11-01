// SIMULADO — catálogo de perfiles de ejemplo. Los valores NO son datos de máquinas reales.
import type { ProfileCatalog } from '../../contracts/settings';
import { AiProvider } from '../../contracts/settings';

const MOCK_MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export function buildMockProfiles(options: { ollamaAvailable: boolean }): ProfileCatalog {
  return {
    machines: [
      {
        id: 'janome_mc550e',
        label: 'Janome MC 550E',
        max_colors: 12,
        hoops: [
          { id: 'hoop_small', label: 'Bastidor chico (simulado)', width_mm: 126, height_mm: 110 },
          { id: 'hoop_large', label: 'Bastidor grande (simulado)', width_mm: 200, height_mm: 200 },
        ],
      },
    ],
    fabrics: [{ id: 'gabardina_inicial', label: 'Gabardina (perfil inicial)' }],
    providers: [
      { id: AiProvider.OpenAI, label: 'OpenAI (nube)', available: true },
      {
        id: AiProvider.Ollama,
        label: 'Modelo local (Ollama)',
        available: options.ollamaAvailable,
        unavailable_reason: options.ollamaAvailable
          ? undefined
          : 'El modelo local no está disponible en el servidor. No se usará otro proveedor en su lugar.',
      },
    ],
    upload_limits: {
      max_bytes: MOCK_MAX_UPLOAD_BYTES,
      accepted_mime_types: ['image/png', 'image/jpeg', 'image/svg+xml'],
    },
  };
}
