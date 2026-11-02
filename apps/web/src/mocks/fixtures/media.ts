// SIMULADO — imágenes y archivos de relleno. No son el resultado de ningún bordado.
// Cada imagen lleva la palabra SIMULADO para que no se confunda con un artefacto real.

function svgDataUri(body: string, width: number, height: number): string {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}">` +
    `<rect width="100%" height="100%" fill="#f4f1ea"/>${body}` +
    `<text x="${width / 2}" y="${height - 8}" text-anchor="middle" font-size="14" fill="#8a2a2a">SIMULADO</text>` +
    '</svg>';
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function mockVectorImage(): string {
  return svgDataUri(
    '<circle cx="100" cy="90" r="60" fill="#3b6ea5"/><rect x="60" y="60" width="80" height="60" fill="#e9c46a"/>',
    200,
    200,
  );
}

export function mockStitchPreviewImage(): string {
  const lines = Array.from({ length: 18 }, (_, i) => {
    const y = 40 + i * 7;
    return `<line x1="50" y1="${y}" x2="150" y2="${y}" stroke="#3b6ea5" stroke-width="1.2"/>`;
  }).join('');
  return svgDataUri(lines, 200, 200);
}

export function mockTextFile(label: string): string {
  return `data:text/plain;charset=utf-8,${encodeURIComponent(`ARCHIVO SIMULADO (${label}). No es un bordado real.\n`)}`;
}
