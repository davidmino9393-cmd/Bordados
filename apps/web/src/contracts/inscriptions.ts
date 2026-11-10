// CAMBIO PROPUESTO (guía 1.3, fuera de OpenAPI v0.1): inscripciones de la imagen para confirmar la frase antes de bordarla.
// GET /projects/{id}/assets/{asset_id}/inscriptions?width_mm&height_mm
// PUT /projects/{id}/assets/{asset_id}/inscriptions?width_mm&height_mm  { confirmed: [{ inscription_id, text }] }
// Forma de services/api/embroidery_api/inscriptions.py. No bloquea nada: propone frases que la persona confirma.

export const InscriptionLayout = { Straight: 'straight', Curved: 'curved' } as const;
export type InscriptionLayout = (typeof InscriptionLayout)[keyof typeof InscriptionLayout];

export interface Inscription {
  inscription_id: string;
  text: string;
  confidence: number;
  layout: InscriptionLayout;
  /** x, y, ancho, alto en píxeles del original. */
  bounds_px: [number, number, number, number];
  letter_height_px: number;
  /** null cuando no se mandó el tamaño. */
  letter_height_mm: number | null;
  small: boolean | null;
  /** La frase guardada; null si no se confirmó o si la lectura cambió desde entonces. */
  confirmed_text: string | null;
}

export interface InscriptionReport {
  schema_version: string;
  /** false si el servidor no tiene el lector de texto instalado. */
  available: boolean;
  unavailable_reason: string | null;
  inscriptions: Inscription[];
  small_below_mm: number;
  duration_ms: number;
  method: string;
}

export interface InscriptionSizeQuery {
  width_mm: number;
  height_mm: number;
}

export interface ConfirmedInscription {
  inscription_id: string;
  text: string;
}
