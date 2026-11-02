# Corrección de complejidad de E

Propósito: reproducir el fallo informado por F sin eliminar geometría para que la entrada pase.

Contenido: [Cambio](#cambio), [Verificación](#verificación), [Límites](#límites), [Referencias](#referencias).

## Cambio

- Referencia PNG existente: 1122×1402 px; 425078 aristas medidas entre las máscaras de sus 3 colores.
- E1 rechazaba sobre 250000 aristas. Nuevo límite genérico: 500000.
- El aumento se acompaña de almacenamiento compacto: byte por vértice y uint32 por arista, en lugar de diccionarios/listas/tuplas por adyacencia.
- Cota del payload lógico de adyacencia para esta entrada: 3275881 bytes, sin contar capacidad extra de arrays ni polígonos de salida. Los inicios compartidos reducen esa cifra; no representa la memoria total del proceso.
- No se redimensiona el raster, no se descartan componentes y no se suavizan huecos. Cada color comprueba aristas recorridas y área exacta contra su máscara.

## Verificación

```powershell
python -m unittest discover -s tests/engine -p 'test_vectorize*.py' -v
```

`test_vectorize_complexity.py` prueba ambas escalas y exige las 425078 aristas originales. Una máscara ajedrez de 512×512, con 524288 aristas, continúa rechazándose de forma controlada.

`baseline-check.json` compara los SVG de los 6 casos planos contra la entrega E1 guardada. `reference-check.json` registra las dos escalas, hashes de salida y advertencias. La revisión independiente comprobó además 300 máscaras multicolor pequeñas con semilla fija y paridad por píxel.

## Límites

- Procesar esta complejidad no demuestra fidelidad visual. La paleta de la referencia sigue siendo casi blanca; la segmentación/color no se corrigió en esta entrega.
- Los SVG resultantes rondan 7 MB. Su transporte y presentación deben considerar ese tamaño; no se guardan duplicados aquí.
- Permanecen las incidencias de fondo/cuántización, parámetros provisionales y H3 pendiente. Sin JEF ni aprobación digital/física.
- La nueva cota no es garantía de memoria o latencia en cualquier servidor. La cuantización nativa de Pillow conserva cancelación cooperativa antes/después.

## Referencias

- [Coordinación paralela](../../../../workers/embroidery/vectorize/COORDINACION.md)
- [Regresión](../../test_vectorize_complexity.py)
- [Entrega anterior](../h2-e1/README.md)
