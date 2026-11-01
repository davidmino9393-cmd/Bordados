# H0-01: inventario estático

Propósito: separar referencias particulares de componentes extraíbles. Ningún script original fue ejecutado ni importado.

Contenido: [Matriz](#matriz), [datos](#datos), [relacionados](#relacionados).

## Matriz

| Archivo | Reutilizable después de extraer | Restricciones y escrituras actuales |
|---|---|---|
| `digitalizar.py` | Utilidades de contornos, curvas y serialización SVG; idea de precedencias | Exige 1122×1402 px; umbrales/recortes fijos, pétalos y ejes manuales, tres tonos. Satin y orden particulares. Escribe SVG y Geometria.json; NO digitalizador general. |
| `reparar_rellenos.py` | Invocación de break_apart, captura binaria y XML | Ejecutable y 3 nombres fijos; selección por texto de style. Sobrescribe SVG; no garantiza conservación de huecos/identidad. Timeout 90 s. |
| `exportar_validar.py` | stdout binario, stderr, timeout; relectura y métricas JEF | 2 ejecutables y archivos fijos; exporta JEF/JSON/plan, rasteriza con Inkscape. Preview de plan reemplazada luego por auditoría. Timeout 300/90 s. |
| `auditar.py` | Parser binario acotado, relectura, métricas y preview desde JEF | Paleta/nombres fijos; ≤3 colores, SQ20b/código 4, ≤200 mm y puntada <6 mm. Usa assert; HTML específico. Escribe PNG, JSON y HTML. |
| `informe.py` | Presentación de mediciones separadas de prueba física | Texto, fecha, versiones y perfil del logo fijos. Consume 3 auditorías en orden; sobrescribe informe. |
| `crear_version_pequena.py` | Regeneración desde SVG; auditoría a otra escala | Ajustes por IDs SOCKS/A/e, factor calibrado, 3 tonos, código 2 y área 130×120. Acepta globalmente “Satin has no rungs”: no trasladar esa excepción. Escribe SVG/JEF/PNG/JSON/informe. |
| `reproducir.mjs` | Orquestación secuencial y temporal de job | ANIME_PYTHON con fallback local; instala solo pyembroidery; factor 1.00134; timeout 600 s por script. Copia con force al original. No ejecutarlo en esta fase. |
| `requirements.txt` | Versiones históricas fijadas | numpy 2.3.5, Pillow 12.3.0, pyembroidery 1.5.1, lxml 6.1.1. No fija Python/Node ni motor; no demuestra instalación reproducible. |

## Datos

- Grande: SVG InkStitch → Optimizado.jef; auditoría guardada: 150×142.8 mm, 6789 puntadas, código 4.
- Pequeña: SVG 13x12 InkStitch → 13x12.jef; auditoría guardada: 126.2×120 mm, 5600 puntadas, código 2.
- Valores históricos, no regenerados ni aprobados en tela. Conservar ambas carpetas, incluidos círculo, inicial, logs y referencia.
- No reutilizar excepciones globales de satin, densidades ni límites de máquina como reglas universales.

## Relacionados

[Entorno](environment.md), [índice y hashes](source-inventory.json), [plan](../../../PLAN_MAESTRO.md), [contratos](../../../CONTRATOS_Y_CALIDAD.md).
