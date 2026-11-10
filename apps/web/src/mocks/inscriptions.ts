// SIMULADO — inscripciones fijas para recorrer la pantalla; las lecturas reales las hace el servidor (guía 1.3).
import {
  InscriptionLayout,
  type Inscription,
  type InscriptionReport,
  type InscriptionSizeQuery,
} from '../contracts/inscriptions';

const SMALL_BELOW_MM = 5;
const ORIGINAL_PX = { width: 2880, height: 1440 };

const READINGS: Omit<Inscription, 'letter_height_mm' | 'small' | 'confirmed_text'>[] = [
  {
    inscription_id: 'inscription_1', text: 'MUNICIPALIDAD DE EL FORTÍN', confidence: 0.998, layout: InscriptionLayout.Curved,
    bounds_px: [242, 349, 660, 660], letter_height_px: 50,
  },
  {
    inscription_id: 'inscription_2', text: '# ConTodos!', confidence: 0.97, layout: InscriptionLayout.Straight,
    bounds_px: [1700, 867, 996, 169], letter_height_px: 136,
  },
];

export function simulatedInscriptions(size: InscriptionSizeQuery, confirmed?: Map<string, string>): InscriptionReport {
  const scale = Math.min(size.width_mm / ORIGINAL_PX.width, size.height_mm / ORIGINAL_PX.height);
  return {
    schema_version: '0.1-inscriptions',
    available: true,
    unavailable_reason: null,
    inscriptions: READINGS.map((reading) => {
      const mm = Math.round(reading.letter_height_px * scale * 10) / 10;
      return { ...reading, letter_height_mm: mm, small: mm < SMALL_BELOW_MM, confirmed_text: confirmed?.get(reading.inscription_id) ?? null };
    }),
    small_below_mm: SMALL_BELOW_MM,
    duration_ms: 0,
    method: 'SIMULADO',
  };
}
