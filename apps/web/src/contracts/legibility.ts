// CAMBIO PROPUESTO (orden 3.2, fuera de OpenAPI v0.1): aviso de legibilidad previo a generar.
// GET /projects/{id}/assets/{asset_id}/legibility?width_mm&height_mm&color_limit&hoop_width_mm&hoop_height_mm
// Forma de services/api/embroidery_api/legibility.py. No bloquea nada: informa con números medidos.

export interface LegibilityMinimumSize {
  already_legible: boolean;
  scale_factor: number;
  ink_width_mm: number;
  ink_height_mm: number;
  /** null cuando no se mandó el bastidor. */
  fits_in_hoop: boolean | null;
  message: string;
}

export interface LegibilityMarginOption {
  ink_bbox_px: [number, number, number, number];
  gain_percent: number;
  ink_width_mm_now: number;
  ink_height_mm_now: number;
  ink_width_mm_cropped: number;
  ink_height_mm_cropped: number;
  message: string;
}

export interface LegibilityCheck {
  schema_version: string;
  requested_width_mm: number;
  requested_height_mm: number;
  ink_width_mm: number;
  ink_height_mm: number;
  /** Fracción (0–1) del largo de trazo más angosta que 0,6 mm al tamaño pedido. */
  thin_share_below_0_6_mm: number;
  thin_share_below_0_8_mm: number;
  ink_area_share_below_0_6_mm: number;
  warn: boolean;
  /** Texto con números; solo viene cuando `warn` es true. */
  message: string | null;
  minimum_size: LegibilityMinimumSize;
  margin_option: LegibilityMarginOption | null;
  palette_cleaning_applied: boolean;
  inks: string[];
  method: string;
}

export interface LegibilityQuery {
  width_mm: number;
  height_mm: number;
  color_limit: number;
  hoop_width_mm?: number;
  hoop_height_mm?: number;
}
