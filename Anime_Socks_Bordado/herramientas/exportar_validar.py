"""Ejecuta el motor instalado de Ink/Stitch y relee sus salidas.
Guarda logs originales. No considera una vista vectorial como simulación.
"""
from pathlib import Path
import sys,argparse,subprocess,json,time,math,collections,struct,hashlib
ap=argparse.ArgumentParser();ap.add_argument('--salida',required=True);ap.add_argument('--vendor');ap.add_argument('--solo',default='optimizado');a=ap.parse_args()
if a.vendor:sys.path.append(a.vendor)
import pyembroidery as pe
OUT=Path(a.salida);WORK=OUT/'trabajo';WORK.mkdir(exist_ok=True)
INK=r'C:\Users\david\AppData\Roaming\inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe'
INSC=r'C:\Program Files\Inkscape\bin\inkscape.com'
def run(src,extension,output,*params,timeout=300):
    cmd=[INK,'--extension='+extension,*params,str(OUT/src)]
    t=time.monotonic();p=subprocess.run(cmd,capture_output=True,timeout=timeout)
    (WORK/(Path(output).name+'.stderr.txt')).write_bytes(p.stderr)
    print(json.dumps({'archivo':output,'codigo':p.returncode,'bytes':len(p.stdout),'segundos':round(time.monotonic()-t,2),'stderr':p.stderr.decode('utf-8',errors='replace')[:3000]},ensure_ascii=False),flush=True)
    if p.returncode or not p.stdout:raise RuntimeError('Falló '+output)
    (OUT/output).write_bytes(p.stdout)
    return p.stdout

def metrics(filename):
    pat=pe.read(str(OUT/filename),settings={'trims':True,'trim_at':3,'trim_distance':None,'clipping':True});s=pat.stitches
    counts=collections.Counter(v[2]&pe.COMMAND_MASK for v in s)
    bounds=pat.bounds();lengths=[];jump_len=0
    for i in range(1,len(s)):
        dist=math.hypot(s[i][0]-s[i-1][0],s[i][1]-s[i-1][1])/10
        cmd=s[i][2]&pe.COMMAND_MASK
        if cmd==pe.STITCH:lengths.append(dist)
        elif cmd==pe.JUMP:jump_len+=dist
    b=(OUT/filename).read_bytes()
    return {'archivo':filename,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'ancho_mm':(bounds[2]-bounds[0])/10,'alto_mm':(bounds[3]-bounds[1])/10,'colores_lista':len(pat.threadlist),'puntadas':counts[pe.STITCH],'saltos_comandos':counts[pe.JUMP],'cortes_decodificados':counts[pe.TRIM],'cambios_color':counts[pe.COLOR_CHANGE],'fin':counts[pe.END],'recorrido_saltos_mm':jump_len,'puntada_max_mm':max(lengths,default=0),'puntadas_menores_0_3_mm':sum(0<x<.3 for x in lengths),'hoop_cabecera':struct.unpack_from('<I',b,32)[0],'limites_01mm':list(bounds)}

def png(src,out):
    p=subprocess.run([INSC,str(OUT/src),'--export-filename='+str(OUT/out),'--export-width=1600','--export-background=white','--export-background-opacity=1'],capture_output=True,timeout=90)
    if p.returncode or not(OUT/out).exists():raise RuntimeError(p.stderr.decode(errors='replace'))

if a.solo in ['optimizado','todos']:
    run('Anime_Socks_InkStitch.svg','output','Anime_Socks_Optimizado.jef','--format=jef','--trims=true')
    run('Anime_Socks_InkStitch.svg','output','trabajo/Anime_Socks_Optimizado.json','--format=json')
    run('Anime_Socks_InkStitch.svg','stitch_plan_preview','trabajo/Anime_Socks_Plan.svg','--move-to-side=False','--layer-visibility=hidden','--needle-points=False','--render-jumps=True','--render-mode=simple')
    png('trabajo/Anime_Socks_Plan.svg','Anime_Socks_Preview.png')
    m=metrics('Anime_Socks_Optimizado.jef');(WORK/'Metricas_Optimizado.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m),flush=True)
if a.solo in ['inicial','todos']:
    run('trabajo/Anime_Socks_Inicial.svg','output','trabajo/Anime_Socks_Inicial.jef','--format=jef','--trims=true')
    m=metrics('trabajo/Anime_Socks_Inicial.jef');(WORK/'Metricas_Inicial.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m),flush=True)
if a.solo in ['circulo','todos']:
    run('trabajo/Anime_Socks_Con_Circulo.svg','output','Anime_Socks_Con_Circulo.jef','--format=jef','--trims=true')
    m=metrics('Anime_Socks_Con_Circulo.jef');(WORK/'Metricas_Circulo.json').write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m),flush=True)
