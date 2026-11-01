export interface SizeMm {
  width_mm: number;
  height_mm: number;
}

/**
 * Estimación `contain`: mayor tamaño con la proporción de la imagen dentro del área.
 * Es solo una ayuda visual; la medida real sale del archivo releído por el backend.
 */
export function estimateContain(
  aspectWidthPx: number,
  aspectHeightPx: number,
  area: SizeMm,
): SizeMm | null {
  if (aspectWidthPx <= 0 || aspectHeightPx <= 0 || area.width_mm <= 0 || area.height_mm <= 0) {
    return null;
  }
  const scale = Math.min(area.width_mm / aspectWidthPx, area.height_mm / aspectHeightPx);
  return { width_mm: aspectWidthPx * scale, height_mm: aspectHeightPx * scale };
}
