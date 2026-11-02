#!/usr/bin/env python3
"""Genera el conjunto SINTETICO de imagenes de prueba para H2 (14 imagenes) y su manifest.json.
Solo biblioteca estandar de Python (sin Pillow): un dibujador propio con bordes suavizados.
Las letras se trazan con una tipografia propia hecha de lineas (sin licencias de terceros).
Los 2 JPEG se convierten con System.Drawing de Windows (PowerShell).
Uso:  python generar_imagenes.py          (escribe en la carpeta donde esta el script)"""
import hashlib, json, math, os, pathlib, struct, subprocess, sys, zlib

RAIZ = pathlib.Path(__file__).resolve().parent
NUEVOS = RAIZ / 'nuevos'
NUEVOS.mkdir(exist_ok=True)
BLANCO, NEGRO = (255, 255, 255), (30, 30, 30)
NAVY, NARANJA, VERDE, VERDE_OSC = (20, 40, 90), (255, 153, 0), (46, 139, 87), (20, 80, 50)


class Img:
    def __init__(s, w, h, fondo=None):
        s.w, s.h = w, h
        s.buf = bytearray(bytes(fondo + (255,)) * (w * h)) if fondo else bytearray(w * h * 4)
        s.transparente = fondo is None

    def fill(s, bbox, sdf, color, opacity=1.0):
        x0, y0, x1, y1 = bbox
        x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(s.w, int(x1) + 1), min(s.h, int(y1) + 1)
        buf, w = s.buf, s.w
        fn = color if callable(color) else None
        for y in range(y0, y1):
            fila = y * w
            for x in range(x0, x1):
                d = sdf(x + .5, y + .5)
                if d >= .5:
                    continue
                a = (.5 - d) if d > -.5 else 1.0
                a *= opacity
                if a <= 0:
                    continue
                r, g, b = fn(x + .5, y + .5) if fn else color
                i = (fila + x) * 4
                da = buf[i + 3] / 255
                oa = a + da * (1 - a)
                buf[i] = min(255, int((r * a + buf[i] * da * (1 - a)) / oa + .5))
                buf[i + 1] = min(255, int((g * a + buf[i + 1] * da * (1 - a)) / oa + .5))
                buf[i + 2] = min(255, int((b * a + buf[i + 2] * da * (1 - a)) / oa + .5))
                buf[i + 3] = min(255, int(oa * 255 + .5))

    def png(s, ruta):
        w, h = s.w, s.h
        if s.transparente:
            tipo, paso = 6, 4
            filas = [b'\x00' + bytes(s.buf[y * w * 4:(y + 1) * w * 4]) for y in range(h)]
        else:
            tipo, paso = 2, 3
            filas = []
            for y in range(h):
                fila = s.buf[y * w * 4:(y + 1) * w * 4]
                filas.append(b'\x00' + bytes(fila[0::4]) if False else b'\x00' + bytes(v for i, v in enumerate(fila) if i % 4 != 3))
        def trozo(t, d):
            c = struct.pack('>I', len(d)) + t + d
            return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        datos = b'\x89PNG\r\n\x1a\n' + trozo(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, tipo, 0, 0, 0)) + \
            trozo(b'IDAT', zlib.compress(b''.join(filas), 9)) + trozo(b'IEND', b'')
        pathlib.Path(ruta).write_bytes(datos)


# ---- formas (distancia con signo: negativo adentro) ----
def circulo(cx, cy, r):
    return (lambda x, y: math.hypot(x - cx, y - cy) - r), (cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)


def anillo(cx, cy, r, w):
    return (lambda x, y: abs(math.hypot(x - cx, y - cy) - r) - w / 2), (cx - r - w, cy - r - w, cx + r + w, cy + r + w)


def poligono(pts):
    n = len(pts)
    def f(x, y):
        d, dentro, j = 1e18, False, n - 1
        for i in range(n):
            xi, yi = pts[i]; xj, yj = pts[j]
            ex, ey, wx, wy = xj - xi, yj - yi, x - xi, y - yi
            t = max(0, min(1, (wx * ex + wy * ey) / (ex * ex + ey * ey)))
            dx, dy = wx - ex * t, wy - ey * t
            d = min(d, dx * dx + dy * dy)
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                dentro = not dentro
            j = i
        d = math.sqrt(d)
        return -d if dentro else d
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return f, (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)


def trazo(pts, w, cerrado=False):
    segs = list(zip(pts, pts[1:] + ([pts[0]] if cerrado else [])))
    hw = w / 2
    def f(x, y):
        d = 1e18
        for (ax, ay), (bx, by) in segs:
            ex, ey, wx, wy = bx - ax, by - ay, x - ax, y - ay
            l = ex * ex + ey * ey
            t = 0 if l == 0 else max(0, min(1, (wx * ex + wy * ey) / l))
            dx, dy = wx - ex * t, wy - ey * t
            q = dx * dx + dy * dy
            if q < d:
                d = q
        return math.sqrt(d) - hw
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return f, (min(xs) - hw - 1, min(ys) - hw - 1, max(xs) + hw + 1, max(ys) + hw + 1)


def recorte(f1, f2):                     # interseccion
    return lambda x, y: max(f1(x, y), f2(x, y))


def elipse_pts(cx, cy, rx, ry, n=32):
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


# ---- letras propias, cuadricula 4 x 6 ----
GL = {'N': [([(0, 6), (0, 0), (4, 6), (4, 0)], 0)], 'V': [([(0, 0), (2, 6), (4, 0)], 0)],
      'A': [([(0, 6), (2, 0), (4, 6)], 0), ([(.8, 4), (3.2, 4)], 0)], 'M': [([(0, 6), (0, 0), (2, 3.5), (4, 0), (4, 6)], 0)],
      'K': [([(0, 0), (0, 6)], 0), ([(4, 0), (0, 3.5), (4, 6)], 0)], 'L': [([(0, 0), (0, 6), (4, 6)], 0)],
      'U': [([(0, 0), (0, 4.2), (.6, 5.4), (2, 6), (3.4, 5.4), (4, 4.2), (4, 0)], 0)],
      'T': [([(0, 0), (4, 0)], 0), ([(2, 0), (2, 6)], 0)], 'E': [([(4, 0), (0, 0), (0, 6), (4, 6)], 0), ([(0, 3), (3, 3)], 0)],
      'R': [([(0, 6), (0, 0), (3, 0), (4, .8), (4, 2.2), (3, 3), (0, 3)], 0), ([(2, 3), (4, 6)], 0)],
      'O': [(elipse_pts(2, 3, 2, 3), 1)]}


def ancho_texto(s, h, sep):
    e = h / 6
    return sum((4 * e + sep) if c != ' ' else 2.2 * e for c in s) - sep


def texto(img, s, x, y, h, grosor, color, sep):
    e = h / 6
    for c in s:
        if c == ' ':
            x += 2.2 * e
            continue
        for pts, cerrado in GL[c]:
            f, bb = trazo([(x + px * e, y + py * e) for px, py in pts], grosor, bool(cerrado))
            img.fill(bb, f, color)
        x += 4 * e + sep


def jpeg_desde_png(png, jpg, calidad=88):
    ps = ("Add-Type -AssemblyName System.Drawing;$i=[System.Drawing.Image]::FromFile('%s');"
          "$c=[System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders()|Where-Object{$_.MimeType -eq 'image/jpeg'};"
          "$p=New-Object System.Drawing.Imaging.EncoderParameters(1);"
          "$p.Param[0]=New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality,[long]%d);"
          "$i.Save('%s',$c,$p);$i.Dispose()") % (str(png), calidad, str(jpg))
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True, capture_output=True)
    os.remove(png)


# ---- las 14 imagenes ----
def logo_sol():
    im = Img(1200, 900, BLANCO)
    f, bb = anillo(600, 450, 380, 28); im.fill(bb, f, NAVY)
    f, bb = circulo(600, 450, 170); im.fill(bb, f, NARANJA)
    for k in range(12):
        a = math.radians(k * 30)
        f, bb = trazo([(600 + 225 * math.cos(a), 450 + 225 * math.sin(a)), (600 + 320 * math.cos(a), 450 + 320 * math.sin(a))], 38)
        im.fill(bb, f, NARANJA)
    return im


def logo_hoja():
    im = Img(1000, 1000)
    c1, _ = circulo(750, 750, 500); c2, _ = circulo(250, 250, 500)
    im.fill((240, 240, 760, 760), recorte(c1, c2), VERDE)
    f, bb = trazo([(250, 750), (700, 300)], 24); im.fill(bb, f, VERDE_OSC)
    f, bb = trazo([(250, 750), (170, 830)], 30); im.fill(bb, f, VERDE_OSC)
    return im


def logo_escudo():
    im = Img(1000, 1200, BLANCO)
    esc, bb = poligono([(150, 150), (850, 150), (850, 600), (500, 1080), (150, 600)])
    im.fill(bb, esc, (200, 30, 40))
    banda = lambda x, y: max(abs(x - 500) - 400, abs(y - 375) - 75)
    im.fill((150, 300, 850, 450), recorte(esc, banda), NAVY)
    estrella = [(500 + (150 if k % 2 == 0 else 60) * math.sin(math.pi * k / 5), 700 - (150 if k % 2 == 0 else 60) * math.cos(math.pi * k / 5)) for k in range(10)]
    f, bb = poligono(estrella); im.fill(bb, f, (250, 200, 40))
    return im


def logo_ola():
    im = Img(1200, 800, BLANCO)
    for base, fase, col in ((250, 0, (10, 60, 140)), (400, 1.5, (30, 120, 200)), (550, 3.0, (120, 190, 235))):
        fx = lambda x, b=base, p=fase: b + 60 * math.sin(2 * math.pi * x / 400 + p)
        dfx = lambda x, p=fase: 60 * 2 * math.pi / 400 * math.cos(2 * math.pi * x / 400 + p)
        def banda(x, y, fx=fx, dfx=dfx):
            d = abs(y - (fx(x) + 45)) - 45
            return max(d / math.sqrt(1 + dfx(x) ** 2), abs(x - 600) - 500)
        im.fill((100, base - 120, 1100, base + 170), banda, col)
    return im


def linea_casa():
    im = Img(1000, 1000, BLANCO)
    for pts, cer in (([(200, 450), (500, 180), (800, 450)], False), ([(260, 400), (260, 820), (740, 820), (740, 400)], False),
                     ([(440, 820), (440, 600), (560, 600), (560, 820)], False), ([(650, 300), (650, 200), (720, 200), (720, 360)], False)):
        f, bb = trazo(pts, 16, cer); im.fill(bb, f, NEGRO)
    for cx in (360, 640):
        f, bb = anillo(cx, 560, 45, 16); im.fill(bb, f, NEGRO)
    return im


def svg_arbol():
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000">\n'
            '<g fill="none" stroke="#1e1e1e" stroke-width="14" stroke-linecap="round" stroke-linejoin="round">\n'
            '<path d="M470,900 C470,760 480,700 500,620 C520,700 530,760 530,900"/>\n'
            '<path d="M500,620 L380,480"/><path d="M500,620 L620,480"/><path d="M500,560 L500,400"/>\n'
            '<circle cx="500" cy="300" r="170"/><circle cx="330" cy="430" r="110"/><circle cx="670" cy="430" r="110"/>\n'
            '<path d="M300,900 H700"/></g></svg>\n')


def letras_nova():
    im = Img(1200, 600, BLANCO)
    h, sep = 300, 70
    x0 = (1200 - ancho_texto('NOVA', h, sep)) / 2
    texto(im, 'NOVA', x0, 140, h, 46, NAVY, sep)
    f, bb = trazo([(x0, 510), (x0 + ancho_texto('NOVA', h, sep), 510)], 24); im.fill(bb, f, NARANJA)
    return im


def monograma_mk():
    im = Img(1000, 1000, BLANCO)
    f, bb = anillo(500, 500, 420, 40); im.fill(bb, f, NAVY)
    h, sep = 420, 90
    texto(im, 'MK', (1000 - ancho_texto('MK', h, sep)) / 2, 290, h, 60, NARANJA, sep)
    return im


def anillo_doble():
    im = Img(1000, 1000, BLANCO)
    f, bb = anillo(500, 500, 330, 120); im.fill(bb, f, NAVY)
    f, bb = anillo(500, 500, 140, 70); im.fill(bb, f, NARANJA)
    return im


def svg_huecos():
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000">\n'
            '<path fill="#0f766e" fill-rule="evenodd" d="M230,150 H770 A80,80 0 0 1 850,230 V770 A80,80 0 0 1 770,850 H230 A80,80 0 0 1 150,770 V230 A80,80 0 0 1 230,150 Z '
            'M300,350 a100,100 0 1,0 200,0 a100,100 0 1,0 -200,0 Z M560,560 a110,110 0 1,0 220,0 a110,110 0 1,0 -220,0 Z '
            'M330,680 a50,50 0 1,0 100,0 a50,50 0 1,0 -100,0 Z"/></svg>\n')


def dificil_lineas_finas():
    im = Img(1200, 1200, BLANCO)
    for r in range(60, 580, 45):
        f, bb = anillo(600, 600, r, 2); im.fill(bb, f, NEGRO)
    for k in range(24):
        a = math.radians(k * 15)
        f, bb = trazo([(600 + 40 * math.cos(a), 600 + 40 * math.sin(a)), (600 + 560 * math.cos(a), 600 + 560 * math.sin(a))], 2)
        im.fill(bb, f, NEGRO)
    return im


def dificil_texto_chico():
    im = Img(1200, 800, BLANCO)
    f, bb = anillo(600, 400, 330, 20); im.fill(bb, f, NAVY)
    texto(im, 'LUNA', (1200 - ancho_texto('LUNA', 150, 50)) / 2, 270, 150, 26, NAVY, 50)
    t = 'NOVA TALLER'
    texto(im, t, (1200 - ancho_texto(t, 22, 5)) / 2, 470, 22, 3, NAVY, 5)
    return im


def dificil_degradado():
    im = Img(1200, 1200, (245, 245, 245))
    sombra = lambda x, y: (math.hypot(x - 600, (y - 960) / .22) - 380) / 40
    im.fill((150, 700, 1050, 1200), sombra, (60, 60, 60), 0.55)
    def esfera(x, y):
        t = min(1.0, math.hypot(x - 500, y - 430) / 520)
        return (int(255 + (190 - 255) * t), int(200 + (40 - 200) * t), int(90 + (30 - 90) * t))
    f, bb = circulo(600, 560, 380); im.fill(bb, f, esfera)
    return im


def jpeg_simple():
    im = Img(1000, 1000, BLANCO)
    for pts in ([(150, 780), (450, 300), (750, 780)], [(500, 780), (700, 450), (900, 780)]):
        f, bb = poligono(pts); im.fill(bb, f, NAVY)
    f, bb = circulo(760, 260, 90); im.fill(bb, f, NARANJA)
    return im


DER = {'owner': 'Generado por código', 'license': 'Propia, uso interno de prueba', 'permission_confirmed': True}
# (id, archivo, categoria, formato, constructor, colores, tamano_mm, resultado, texto, motivo, trampas, nota)
LISTA = [
    ('logo-sol-01', 'logo_sol_01.png', 'flat_logo', 'png', logo_sol, 2, (100, 75), 'automatic', None, None, ['rayos redondeados cerca del aro'], None),
    ('logo-hoja-01', 'logo_hoja_01.png', 'transparency', 'png', logo_hoja, 2, (90, 90), 'automatic', None, None, ['fondo transparente', 'nervadura fina dentro de la hoja'], None),
    ('logo-escudo-01', 'logo_escudo_01.png', 'flat_logo', 'png', logo_escudo, 3, (80, 96), 'automatic', None, None, ['estrella con puntas agudas'], None),
    ('logo-ola-01', 'logo_ola_01.png', 'few_colors_drawing', 'png', logo_ola, 3, (120, 80), 'automatic', None, None, ['tres azules parecidos'], None),
    ('linea-casa-01', 'linea_casa_01.png', 'line_art', 'png', linea_casa, 1, (80, 80), 'automatic', None, None, ['solo contornos, sin relleno'], 'trazo de unos 1,3 mm a 80 mm'),
    ('linea-arbol-01', 'linea_arbol_01.svg', 'line_art', 'svg', svg_arbol, 1, (80, 80), 'automatic', None, None, ['curvas bezier', 'fondo transparente'], None),
    ('letras-nova-01', 'letras_nova_01.png', 'lettering', 'png', letras_nova, 2, (120, 60), 'automatic', 'NOVA', None, ['letra V y A con ángulos agudos'], 'tipografía propia de líneas'),
    ('monograma-mk-01', 'monograma_mk_01.png', 'lettering', 'png', monograma_mk, 2, (80, 80), 'automatic', 'MK', None, ['letras dentro de un aro cerrado'], 'tipografía propia de líneas'),
    ('anillo-doble-01', 'anillo_doble_01.png', 'closed_curves_with_holes', 'png', anillo_doble, 2, (90, 90), 'automatic', None, None, ['dos huecos concéntricos'], None),
    ('formas-huecos-01', 'formas_huecos_01.svg', 'closed_curves_with_holes', 'svg', svg_huecos, 1, (90, 90), 'automatic', None, None, ['tres huecos (fill-rule evenodd)', 'fondo transparente'], None),
    ('dificil-lineas-finas-01', 'dificil_lineas_finas_01.png', 'expects_review', 'png', dificil_lineas_finas, 1, (80, 80), 'needs_review', None,
     'trazos de unos 0,13 mm de ancho a este tamaño (menos de 1 mm)', ['líneas muy finas', 'muchas líneas cercanas'], None),
    ('dificil-texto-chico-01', 'dificil_texto_chico_01.png', 'expects_review', 'png', dificil_texto_chico, 1, (100, 67), 'needs_review', 'LUNA NOVA TALLER',
     'letras de la segunda línea de unos 1,8 mm de alto (menos de 4 mm)', ['texto muy chico', 'trazo de 3 px'], 'tipografía propia de líneas'),
    ('dificil-degradado-01', 'dificil_degradado_01.jpg', 'expects_review', 'jpeg', dificil_degradado, 3, (90, 90), 'needs_review', None,
     'degradado de color y sombra suave: no se pueden bordar con un solo color por zona', ['degradado', 'sombra difusa', 'ruido JPEG'], None),
    ('jpeg-simple-01', 'jpeg_simple_01.jpg', 'flat_logo', 'jpeg', jpeg_simple, 2, (80, 80), 'automatic', None, None, ['bordes con ruido de compresión JPEG'], None),
]


def main():
    imagenes = []
    for (id_, arch, cat, fmt, fn, cols, (mw, mh), res, txt, motivo, trampas, nota) in LISTA:
        ruta = NUEVOS / arch
        print('generando', arch, flush=True)
        obj = fn()
        item = {'id': id_, 'file': 'nuevos/' + arch, 'design_family': id_, 'variant_of': None, 'category': cat, 'format': fmt}
        if isinstance(obj, str):
            ruta.write_text(obj, encoding='utf-8', newline='\n'); transp = True
        else:
            transp = obj.transparente
            if fmt == 'png':
                obj.png(ruta)
            else:
                tmp = NUEVOS / (arch + '.tmp.png'); obj.png(tmp); jpeg_desde_png(tmp, ruta)
            item['pixel_size'] = {'width': obj.w, 'height': obj.h}
        item.update({'has_transparency': transp, 'contains_text': txt is not None, 'text': txt, 'expected_colors': cols,
                     'target_size_mm': {'width_mm': mw, 'height_mm': mh}, 'expected_outcome': res})
        if motivo:
            item['expected_review_reason'] = motivo
        item['known_traps'] = trampas
        item['rights'] = dict(DER)
        if nota:
            item['notes'] = nota
        item['sha256'] = hashlib.sha256(ruta.read_bytes()).hexdigest()
        imagenes.append(item)
    (RAIZ / 'manifest.json').write_text(json.dumps({'schema_version': '0.1', 'set_name': 'Conjunto sintético H2 (14 imágenes generadas por código; faltan las 2 escalas de Anime Socks)',
                                                    'images': imagenes}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('listo:', len(imagenes), 'imagenes + manifest.json')


main()
