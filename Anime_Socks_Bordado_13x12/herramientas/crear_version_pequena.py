"""Nueva digitalización desde los SVG editables ya validados, no desde el JEF.
Conserva proporciones y parámetros físicos de separación de puntadas.
"""
from pathlib import Path
import argparse,sys,re,json,subprocess,time,collections,math,struct,hashlib,zipfile
from lxml import etree as ET
from PIL import Image,ImageDraw
ap=argparse.ArgumentParser()
ap.add_argument('--original',required=True)
ap.add_argument('--salida',required=True)
ap.add_argument('--vendor',required=True)
ap.add_argument('--factor',type=float,default=120/142.8*120/120.2)
a=ap.parse_args();sys.path.append(a.vendor)
import pyembroidery as pe
src=Path(a.original);out=Path(a.salida);out.mkdir(parents=True,exist_ok=True)
work=out/'trabajo';work.mkdir(exist_ok=True)
IS='{http://inkstitch.org/namespace}';SVG='{http://www.w3.org/2000/svg}'
ink=r'C:\Users\david\AppData\Roaming\inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe'
changes=[]
def scaled(original,dest,configured=True):
    tree=ET.parse(str(src/original));root=tree.getroot()
    for key in ['width','height']:
        mm=float(root.get(key).removesuffix('mm'))*a.factor
        root.set(key,f'{mm:.6f}mm')
    title=root.find(SVG+'title')
    if title is not None:title.text='Anime Socks · versión pequeña · dentro de 130 × 120 mm · Janome MC 550E'
    if configured:
        for p in root.iter(SVG+'path'):
            id=p.get('id','')
            if p.get(IS+'satin_column')=='True':
                if 'SOCKS' in id:
                    p.set(IS+'pull_compensation_mm','0.15')
                    p.set(IS+'center_walk_underlay','False')
                    changes.append({'id':id,'compensacion_mm':.15})
                if 'A_lazo_ascenso' in id or 'satin_e_' in id:
                    p.set(IS+'center_walk_underlay','False')
                    changes.append({'id':id,'center_walk_underlay':False})
            if p.get(IS+'stroke_method')=='running_stitch':
                old=float(p.get(IS+'running_stitch_length_mm','2.3'))
                # Length remains a physical parameter instead of shrinking with geometry.
                if old>2.0 and id!='circulo_fino':p.set(IS+'running_stitch_length_mm','2.0')
    tree.write(str(out/dest),encoding='UTF-8',xml_declaration=True,pretty_print=True)

scaled('Anime_Socks_Vector.svg','Anime_Socks_13x12_Vector.svg',False)
scaled('Anime_Socks_InkStitch.svg','Anime_Socks_13x12_InkStitch.svg')
scaled('Anime_Socks_Con_Circulo.svg','Anime_Socks_13x12_Con_Circulo.svg')

def engine(input,extension,output,*params):
    t=time.monotonic()
    p=subprocess.run([ink,'--extension='+extension,*params,str(out/input)],capture_output=True,timeout=180)
    (work/(Path(output).name+'.stderr.txt')).write_bytes(p.stderr)
    if p.returncode or not p.stdout:raise RuntimeError(p.stderr.decode('utf-8',errors='replace'))
    (out/output).write_bytes(p.stdout)
    print(json.dumps({'archivo':output,'codigo':p.returncode,'bytes':len(p.stdout),'segundos':round(time.monotonic()-t,2)},ensure_ascii=False),flush=True)
    return p.stdout

def audit(filename,preview):
    b=(out/filename).read_bytes();offset=struct.unpack_from('<I',b,0)[0]
    nc,nrecords,hoop=struct.unpack_from('<III',b,24)
    assert offset==116+8*nc and offset+nrecords*2==len(b)
    assert b[-2:]==b'\x80\x10'
    cursor=offset;binary=collections.Counter()
    while cursor<len(b):
        pair=b[cursor:cursor+2];assert len(pair)==2;cursor+=2
        if pair[0]!=0x80:binary['STITCH']+=1;continue
        ctrl=pair[1];assert ctrl in [1,2,16]
        if ctrl==16:assert cursor==len(b);binary['END']+=1;break
        assert cursor+2<=len(b);cursor+=2;binary['JUMP' if ctrl==2 else 'COLOR_CHANGE']+=1
    pat=pe.read(str(out/filename),settings={'trims':True,'trim_at':3,'trim_distance':None,'clipping':True})
    bounds=pat.bounds();width=(bounds[2]-bounds[0])/10;height=(bounds[3]-bounds[1])/10
    assert width<=130.1 and height<=120.1,(width,height,'Supera el área solicitada')
    assert width<140 and height<140 and hoop==2,(width,height,hoop)
    counts=collections.Counter(p[2]&pe.COMMAND_MASK for p in pat.stitches)
    assert binary['STITCH']==counts[pe.STITCH] and counts[pe.END]==1 and len(pat.threadlist)==3
    scale=1800/(bounds[2]-bounds[0]+80);im=Image.new('RGB',(1880,round((bounds[3]-bounds[1]+80)*scale)+80),'white');draw=ImageDraw.Draw(im)
    colors=['#967E88','#EDB3B5','#BF7F85'];thread=0;previous=[0,0];lengths=[];jump_lengths=[];density=collections.Counter()
    def xy(p):return((p[0]-bounds[0]+40)*scale+40,(p[1]-bounds[1]+40)*scale+40)
    for p in pat.stitches:
        assert math.isfinite(p[0]) and math.isfinite(p[1])
        cmd=p[2]&pe.COMMAND_MASK;length=math.hypot(p[0]-previous[0],p[1]-previous[1])/10
        if cmd==pe.STITCH:
            lengths.append(length);density[(math.floor(p[0]/10),math.floor(p[1]/10))]+=1
            draw.line([xy(previous),xy(p)],fill=colors[min(thread,2)],width=max(1,round(.23*10*scale)))
        elif cmd==pe.COLOR_CHANGE:thread+=1
        elif cmd==pe.JUMP:jump_lengths.append(length)
        previous=p
    im.save(out/preview)
    assert max(lengths)<6
    metrics={'archivo':filename,'dimensiones_mm':[width,height],'puntadas':counts[pe.STITCH],'saltos':counts[pe.JUMP],'cortes_codificados':counts[pe.TRIM],'cambios_color':counts[pe.COLOR_CHANGE],'bloques_hilo':len(pat.threadlist),'puntada_max_mm':max(lengths),'recorrido_saltos_mm':sum(jump_lengths),'puntadas_menores_03_mm':sum(0<d<.3 for d in lengths),'max_penetraciones_celda_1mm':density.most_common(8),'cabecera_hoop':hoop,'integridad_binaria':True,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
    (work/(Path(filename).stem+'_Auditoria.json')).write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    return metrics

main='Anime_Socks_13x12_InkStitch.svg';circle='Anime_Socks_13x12_Con_Circulo.svg'
# Check the actual geometry at the new physical size, retain all diagnostics.
diagnostic=engine(main,'troubleshoot','trabajo/Troubleshoot.svg')
tree=ET.fromstring(diagnostic)
warnings=collections.Counter(''.join(t.itertext()) for t in tree.iter(SVG+'text') if t.get('{http://www.inkscape.org/namespaces/inkscape}label')=='Description')
assert not(set(warnings)-{'Satin has no rungs'}),dict(warnings)
engine(main,'output','Anime_Socks_13x12.jef','--format=jef','--trims=true')
engine(circle,'output','Anime_Socks_13x12_Con_Circulo.jef','--format=jef','--trims=true')
engine(main,'stitch_plan_preview','trabajo/Anime_Socks_13x12_Plan.svg','--move-to-side=False','--layer-visibility=hidden','--needle-points=False','--render-jumps=True','--render-mode=simple')
metrics=[audit('Anime_Socks_13x12.jef','Anime_Socks_13x12_Preview.png'),audit('Anime_Socks_13x12_Con_Circulo.jef','Anime_Socks_13x12_Con_Circulo_Preview.png')]
manifest={'factor_geometria':a.factor,'area_solicitada_mm':[130,120],'diagnostico_inkstitch':dict(warnings),'ajustes':changes,'jef':metrics}
(work/'Validacion_13x12.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
m,c=metrics
report=f'''# Anime Socks — versión pequeña para prueba de bordado

## Tamaño y proporciones

Área solicitada: aproximadamente 130 × 120 mm. Se conservó la proporción del logo para que entre en esa área, en lugar de estirar por separado sus ejes.

- Principal sin círculo: **{m['dimensiones_mm'][0]:.1f} × {m['dimensiones_mm'][1]:.1f} mm**.
- Con círculo: **{c['dimensiones_mm'][0]:.1f} × {c['dimensiones_mm'][1]:.1f} mm**.
- Reducción geométrica desde el diseño anterior: factor {a.factor:.8f}.

## Digitalización a la nueva escala

Se redujeron los SVG editables ya corregidos y se regeneraron todas las puntadas con Ink/Stitch 3.2.2. No se encogió el JEF anterior. Se mantuvo la composición, la forma de las letras, las flores y los tres tonos.

Las separaciones físicas se mantienen: satin 0,43 mm, rellenos abiertos de pétalos 0,85 mm, hojas 0,95 mm, capullos 0,75 mm y corazones 0,45 mm. Los contornos y ramas utilizan running de hasta 2 mm para definir mejor las curvas pequeñas; el círculo conserva running simple de 2,5 mm.

En SOCKS se redujo la compensación satin a 0,15 mm y se mantuvo sin underlay adicional. Se retiró center walk de los tramos finos del lazo de A y de e; las columnas más anchas conservan su configuración anterior. Las dos curvas de cada satin tienen nodos correspondientes.

## Métricas medidas desde los JEF

| Medida | Sin círculo | Con círculo |
|---|---:|---:|
| Puntadas | {m['puntadas']} | {c['puntadas']} |
| Saltos, tras interpretar cortes | {m['saltos']} | {c['saltos']} |
| Cortes codificados | {m['cortes_codificados']} | {c['cortes_codificados']} |
| Cambios de color | {m['cambios_color']} | {c['cambios_color']} |
| Bloques de hilo | 3 | 3 |
| Puntada máxima, mm | {m['puntada_max_mm']:.2f} | {c['puntada_max_mm']:.2f} |

Se verificaron longitud de archivo, tabla de hilos, registros, todos los comandos binarios hasta el marcador final, coordenadas y cabecera de bastidor. Se releyeron los JEF con pyembroidery 1.5.1 y se dibujaron las vistas previas desde esas coordenadas reales. Se generó el plan completo con Ink/Stitch.

Diagnóstico a esta escala: {dict(warnings)}. Los avisos de ausencia de rungs son recomendaciones para columnas que aquí emplean el método documentado de nodos correspondientes. No se encontraron otros avisos geométricos en ese diagnóstico.

## Bastidor Janome

Para la primera prueba usar **RE20b, 140 × 200 mm**, coherente con la cabecera JEF del exportador (código 2). Las dimensiones también caben geométricamente en SQ14b de 140 × 140 mm. El JEF no incluye un código exclusivo para SQ14b; no se verificó en la máquina un cambio a ese bastidor. No se alteró artificialmente la cabecera. Comprobar la posición con la función de trazado antes de bordar.

Fuente de tamaños de bastidor: [Janome MC 550E](https://www.janome.ca/product/memory-craft-550e/). Método satin: [Ink/Stitch](https://inkstitch.org/docs/stitches/satin-column/).

## Hilos y prueba

Orden de hilos físicos: **malva grisáceo → rosa pálido → rosa viejo más oscuro**. El JEF muestra aproximaciones de la paleta Janome; elegir los hilos por los tonos del logo y no por nombres como Beige Gray o Umber.

Probar primero en un retazo equivalente a la gabardina del bolso, con estabilizador recortable y los hilos elegidos. Revisar especialmente la legibilidad de SOCKS, las conexiones de Anime, la cobertura de los pétalos y el funcionamiento de los cortes. Los cortes JEF se codifican mediante tres saltos de desplazamiento cero; su ejecución física depende del ajuste de la máquina.

La integridad digital está comprobada. No se realizó un bordado físico ni se cargaron estos archivos en la máquina. Esta reducción requiere su propia muestra aunque la versión grande haya dado buen resultado.

## Reproducción y archivos

Se incluye `herramientas/crear_version_pequena.py`. Requiere Python con Pillow, lxml y pyembroidery; recibe `--original` (carpeta de la versión grande), `--salida`, `--vendor` y opcionalmente `--factor`. Las rutas de Inkscape/InkStitch corresponden a la instalación comprobada en esta computadora.

Las auditorías, diagnóstico y plan están en `trabajo`. Los SVG y las vistas previas son editables/consultables por separado. Se conservaron todos los archivos de la versión grande.

SHA-256 principal: `{m['sha256']}`.
SHA-256 con círculo: `{c['sha256']}`.
'''
(out/'Anime_Socks_13x12_Informe.md').write_text(report,encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False),flush=True)
