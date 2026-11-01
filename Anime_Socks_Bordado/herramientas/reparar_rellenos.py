"""Normaliza las áreas de relleno con Break Apart de Ink/Stitch instalado.
La opción method=0 está verificada en su descriptor .inx.
"""
from pathlib import Path
import argparse,subprocess,json
from lxml import etree as ET
ap=argparse.ArgumentParser();ap.add_argument('--salida',required=True);a=ap.parse_args()
base=Path(a.salida);exe=r'C:\Users\david\AppData\Roaming\inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe'
results=[]
for name in ['Anime_Socks_InkStitch.svg','trabajo/Anime_Socks_Inicial.svg','trabajo/Anime_Socks_Con_Circulo.svg']:
    path=base/name;tree=ET.parse(str(path))
    ids=[e.get('id') for e in tree.iter('{http://www.w3.org/2000/svg}path') if 'fill:none' not in e.get('style','') and 'fill:' in e.get('style','')]
    p=subprocess.run([exe,'--extension=break_apart','--method=0',*['--id='+i for i in ids],str(path)],capture_output=True,timeout=90)
    assert p.returncode==0 and p.stdout,p.stderr.decode(errors='replace')
    ET.fromstring(p.stdout)
    path.write_bytes(p.stdout)
    (base/'trabajo'/(path.stem+'_Reparacion.stderr.txt')).write_bytes(p.stderr)
    results.append({'svg':name,'rellenos_seleccionados':len(ids),'motor':'Ink/Stitch break_apart method=0','codigo':p.returncode})
(base/'trabajo/Reparacion_Rellenos.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results),flush=True)
