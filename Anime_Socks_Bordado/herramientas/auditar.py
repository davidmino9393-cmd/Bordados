"""Auditoría independiente del JEF: cabecera, órdenes, dimensiones y recorrido.
Las imágenes se dibujan con las coordenadas releídas del JEF, sin inventar puntadas.
"""
from pathlib import Path
import sys,argparse,json,struct,math,collections,hashlib
from PIL import Image,ImageDraw
ap=argparse.ArgumentParser();ap.add_argument('--salida',required=True);ap.add_argument('--vendor');a=ap.parse_args()
if a.vendor:sys.path.append(a.vendor)
import pyembroidery as pe
OUT=Path(a.salida);WORK=OUT/'trabajo'
colors=['#967E88','#EDB3B5','#BF7F85'];records=[]

def audit(filename,preview):
    data=(OUT/filename).read_bytes();offset,flags=struct.unpack_from('<II',data,0)
    ncolors,nrecords,hoop=struct.unpack_from('<III',data,24)
    assert offset==116+8*ncolors, 'Tabla de hilos incoherente'
    assert offset+nrecords*2==len(data),'Longitud de registros incoherente'
    assert data[-2:]==b'\x80\x10','Falta marcador final'
    cursor=offset;raw_commands=collections.Counter()
    while cursor<len(data):
        pair=data[cursor:cursor+2];assert len(pair)==2;cursor+=2
        if pair[0]!=0x80:raw_commands['STITCH']+=1;continue
        ctrl=pair[1];assert ctrl in (1,2,16),'Orden JEF desconocida'
        if ctrl==16:assert cursor==len(data),'Datos después del fin';raw_commands['END']+=1;break
        assert cursor+2<=len(data);cursor+=2;raw_commands['JUMP' if ctrl==2 else 'COLOR_CHANGE']+=1
    assert 1<=ncolors<=3 or filename.startswith('trabajo/'),'Colores fuera de alcance'
    raw=pe.read(str(OUT/filename),settings={'trims':False,'trim_distance':None,'clipping':False})
    pat=pe.read(str(OUT/filename),settings={'trims':True,'trim_at':3,'trim_distance':None,'clipping':True})
    s=pat.stitches;b=pat.bounds();w=(b[2]-b[0])/10;h=(b[3]-b[1])/10
    assert w<=200 and h<=200 and hoop==4,'No corresponde al SQ20b'
    assert all(math.isfinite(p[0]) and math.isfinite(p[1]) for p in s)
    assert (s[-1][2]&pe.COMMAND_MASK)==pe.END
    names={pe.STITCH:'STITCH',pe.JUMP:'JUMP',pe.TRIM:'TRIM',pe.COLOR_CHANGE:'COLOR_CHANGE',pe.END:'END',pe.STOP:'STOP'}
    counts=collections.Counter(p[2]&pe.COMMAND_MASK for p in s)
    lengths=[];jumps=[];zero=0;density=collections.Counter();events=[];thread=0;previous=[0,0]
    scale=1800/(b[2]-b[0]+80);size=(1880,round((b[3]-b[1]+80)*scale)+80)
    canvas=Image.new('RGB',size,'white');draw=ImageDraw.Draw(canvas)
    def xy(p):return ((p[0]-b[0]+40)*scale+40,(p[1]-b[1]+40)*scale+40)
    for i,p in enumerate(s):
        cmd=p[2]&pe.COMMAND_MASK;dist=math.hypot(p[0]-previous[0],p[1]-previous[1])/10
        if cmd==pe.STITCH:
            lengths.append(dist)
            if dist==0:zero+=1
            density[(math.floor(p[0]/10),math.floor(p[1]/10))]+=1
            draw.line([xy(previous),xy(p)],fill=colors[min(thread,2)],width=max(1,round(.23*10*scale)))
        elif cmd==pe.JUMP:jumps.append(dist)
        elif cmd==pe.COLOR_CHANGE:thread+=1
        events.append([round(p[0]/10,2),round(p[1]/10,2),names.get(cmd,str(cmd)),thread])
        previous=p
    if preview:canvas.save(OUT/preview)
    longest=max(lengths,default=0);assert longest<6,'Puntada demasiado larga'
    top=density.most_common(10)
    assert raw_commands['STITCH']==counts[pe.STITCH]
    report={'archivo':filename,'dimensiones_mm':[w,h],'colores':len(pat.threadlist),'puntadas':counts[pe.STITCH],'saltos':counts[pe.JUMP],'cortes_explicitos':counts[pe.TRIM],'cambios_color':counts[pe.COLOR_CHANGE],'fin':counts[pe.END],'puntada_max_mm':longest,'puntadas_cero':zero,'puntadas_0_a_03_mm':sum(0<x<.3 for x in lengths),'saltos_total_mm':sum(jumps),'salto_max_comando_mm':max(jumps,default=0),'cabecera':{'offset':offset,'registros_2bytes':nrecords,'bytes':len(data),'hoop_id':hoop,'integridad':True,'ordenes_binarias':dict(raw_commands)},'max_penetraciones_cuadricula_1mm':top,'sha256':hashlib.sha256(data).hexdigest(),'paleta_jef':[{'hex':t.hex_color(),'descripcion':t.description,'catalogo':t.catalog_number} for t in pat.threadlist]}
    (WORK/(Path(filename).stem+'_Auditoria.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    records.append(report)
    return events,report

events,report=audit('Anime_Socks_Optimizado.jef','Anime_Socks_Preview.png')
audit('Anime_Socks_Con_Circulo.jef','trabajo/Anime_Socks_Con_Circulo_Preview.png')
audit('trabajo/Anime_Socks_Inicial.jef',None)
(WORK/'Auditoria_Comparativa.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')

# An offline player of every command read from the final JEF. The physical
# machine's acceleration, tension and fabric behavior are deliberately excluded.
html='''<!doctype html><html lang="es"><meta charset="utf-8"><title>Anime Socks · recorrido JEF</title>
<style>body{font:16px system-ui;margin:20px;background:#faf8f7;color:#4d4248}main{max-width:860px;margin:auto}canvas{width:100%;background:white}nav{display:flex;align-items:center;gap:14px;flex-wrap:wrap}button,input{font:inherit}input[type=range]{flex:1;min-width:180px}label{display:flex;gap:6px;align-items:center}p{line-height:1.5}</style>
<main><h1>Anime Socks · recorrido del JEF</h1><nav><button id="play">Reproducir</button><input id="position" type="range" min="0" value="0" aria-label="Posición del recorrido"><label><input id="jumps" type="checkbox">Mostrar saltos</label><output id="count"></output></nav><canvas id="canvas" width="1000" height="970" aria-label="Secuencia de puntadas de Anime Socks"></canvas><p>Coordenadas releídas del JEF final. El avance recorre todas las órdenes. Los cambios de color y cortes se muestran en el estado; los saltos se dibujan punteados cuando se activa la opción. Esta reproducción no simula tensión, deformación de tela ni la mecánica de la máquina.</p><p id="status" aria-live="polite"></p></main>
<script>const events=__EVENTS__, colors=['#967E88','#EDB3B5','#BF7F85'];const canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d'),range=document.getElementById('position'),jump=document.getElementById('jumps'),button=document.getElementById('play'),count=document.getElementById('count'),status=document.getElementById('status');range.max=events.length;range.value=events.length;let playing=false,last=0;const xs=events.map(e=>e[0]),ys=events.map(e=>e[1]),xmin=Math.min(...xs),ymin=Math.min(...ys),width=Math.max(...xs)-xmin,height=Math.max(...ys)-ymin,scale=Math.min(940/width,900/height);function point(e){return[(e[0]-xmin)*scale+30,(e[1]-ymin)*scale+30]}function draw(){ctx.clearRect(0,0,1000,970);ctx.lineCap='round';let cuts=0,changes=0,stitches=0;for(let i=1;i<Number(range.value);i++){const e=events[i],prev=events[i-1];if(e[2]==='TRIM')cuts++;if(e[2]==='COLOR_CHANGE')changes++;if(e[2]==='STITCH'||(e[2]==='JUMP'&&jump.checked)){ctx.strokeStyle=e[2]==='JUMP'?'#87969d':colors[Math.min(e[3],2)];ctx.setLineDash(e[2]==='JUMP'?[3,4]:[]);ctx.lineWidth=e[2]==='JUMP'?1:.23*scale;ctx.beginPath();ctx.moveTo(...point(prev));ctx.lineTo(...point(e));ctx.stroke();if(e[2]==='STITCH')stitches++;}}count.value=range.value+' / '+events.length;status.textContent=stitches+' puntadas · '+cuts+' cortes · '+changes+' cambios de color';}range.oninput=()=>{playing=false;button.textContent='Reproducir';draw()};jump.onchange=draw;button.onclick=()=>{playing=!playing;if(playing&&Number(range.value)>=events.length)range.value=0;button.textContent=playing?'Pausar':'Reproducir';last=0;requestAnimationFrame(tick)};function tick(t){if(!playing)return;if(!last)last=t;range.value=Math.min(events.length,Number(range.value)+Math.max(1,Math.floor((t-last)*1.2)));last=t;draw();if(Number(range.value)>=events.length){playing=false;button.textContent='Reproducir'}else requestAnimationFrame(tick)}draw();</script></html>'''
html=html.replace('__EVENTS__',json.dumps(events,separators=(',',':')))
(OUT/'Anime_Socks_Simulacion.html').write_text(html,encoding='utf-8')
print(json.dumps(records,ensure_ascii=False),flush=True)
