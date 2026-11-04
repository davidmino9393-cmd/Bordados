import csv, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
source=ROOT/'tests/calibration/h3/planilla_h3.csv'
target=ROOT/'tests/engine/evidence/h3-measurement/mediciones.csv'
target.parent.mkdir(parents=True,exist_ok=True)
fields=['elemento','fila','eje_medicion','parametro_programado','valor_programado','objetivo_dimension_mm','dimension_digital_mm','tolerancia_estudio_mm','incertidumbre_estimada_mm','lectura_1_bastidor_mm','lectura_2_bastidor_mm','lectura_3_bastidor_mm','media_bastidor_mm','dimension_fuera_30min_mm','error_vs_nominal_mm','error_vs_digital_mm','longitud_10_intervalos_mm','separacion_observada_mm','aspecto','roturas','fruncido','resultado_estudio','instrumento','notas']
sys.path.insert(0,str(ROOT/'tests/calibration/h3'))
import planilla_h3 as planilla
import generar_muestra as sample
import pyembroidery
jef=ROOT/'tests/calibration/h3/muestra_h3.jef'
pattern=pyembroidery.read(str(jef))
needles=[(x*.1+sample.SHEET_WIDTH_MM/2,y*.1+sample.SHEET_HEIGHT_MM/2) for x,y,c in pattern.stitches if c & pyembroidery.COMMAND_MASK == pyembroidery.STITCH]
digital_y={}
for identifier,_,_,_,(x0,x1,y0,y1) in planilla.elementos():
    points=[(x,y) for x,y in needles if x0<=x<=x1 and y0<=y<=y1]
    digital_y[identifier]=round(max(y for x,y in points)-min(y for x,y in points),2)
rows=[]
for item in csv.DictReader(source.open(encoding='utf8')):
    row=item['fila']
    goal=float(item['valor_nominal']) if row=='A' else {'B':3.,'C':3.,'D':12.,'E':25.}[row]
    tol=max(.2,.05*goal) if row=='A' else (.2 if row in ('B','C') else .5)
    for axis in ('X','Y') if row=='D' else ('X',):
        rows.append(dict(elemento=item['elemento']+'_'+axis if row=='D' else item['elemento'],fila=row,eje_medicion=axis,parametro_programado=item['variable'],valor_programado=item['valor_nominal'],objetivo_dimension_mm=f'{goal:g}',dimension_digital_mm=item['ancho_o_lado_digital_mm'] if axis=='X' else f'{digital_y[item["elemento"]]:g}',tolerancia_estudio_mm=f'{tol:g}'))
for axis,goal in [('X',140),('Y',150)]:
    rows.append(dict(elemento='MARCO_'+axis,fila='MARCO',eje_medicion=axis,parametro_programado='dimension_'+axis,valor_programado=str(goal),objetivo_dimension_mm=str(goal),dimension_digital_mm=str(goal),tolerancia_estudio_mm='1'))
with target.open('w',encoding='utf8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields)
    writer.writeheader();writer.writerows(rows)
assert len(rows)==39
record={'source_csv_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'jef_sha256':hashlib.sha256(jef.read_bytes()).hexdigest(),'rows':len(rows),'physical_measurements_present':False,'thresholds':'proposed study criteria, not calibrated production tolerances'}
(target.parent/'preparation.json').write_text(json.dumps(record,indent=2),encoding='utf8')
print(json.dumps(record,indent=2))

