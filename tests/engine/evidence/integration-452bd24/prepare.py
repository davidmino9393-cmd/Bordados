"""Prepare an integration Git tree without changing refs or the actual index."""
import argparse, hashlib, json, os, re, subprocess, zipfile
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--repo',required=True,type=Path)
p.add_argument('--main',required=True)
p.add_argument('--motor',required=True)
p.add_argument('--out',required=True,type=Path)
a=p.parse_args()
repo=a.repo.resolve(); out=a.out.resolve()
assert out.is_relative_to(repo), 'Scratch output must be inside the workspace'
out.mkdir(parents=True,exist_ok=True)
index=out/'scratch.index'
assert not index.exists(), 'Use a fresh output directory'
commands=[]
def git(*args,env=None,data=None,ok=(0,)):
    commands.append(['git',*args])
    r=subprocess.run(['git',*args],cwd=repo,env=env,input=data,capture_output=True)
    if r.returncode not in ok:
        raise RuntimeError(r.stderr.decode(errors='replace')+r.stdout.decode(errors='replace'))
    return r.stdout.decode('utf8')
before={ref:git('log','-1','--format=%H',ref).strip() for ref in ('main','codex/motor')}
index_path=Path(git('rev-parse','--git-path','index').strip())
if not index_path.is_absolute(): index_path=repo/index_path
index_sha=hashlib.sha256(index_path.read_bytes()).hexdigest() if index_path.exists() else None
merged=git('merge-tree','--write-tree',a.main,a.motor,ok=(0,1))
(out/'merge-tree.txt').write_text(merged,encoding='utf8')
tree=merged.splitlines()[0]
conflicts=sorted(set(re.findall(r'^\d{6} [a-f0-9]{40} [123]\t(.+)$',merged,re.M)))
path='workers/embroidery/vectorize/CONTINUAR.md'
assert not conflicts or conflicts==[path], f'Unexpected conflicts: {conflicts}'
resolved=f'''# Continuar motor integrado (preparación, sin merge a main)

Propósito: retomar el árbol candidato sin confundir evidencia histórica con trabajo pendiente. Fecha: 2026-11-03.

Contenido: [Base](#base), [Estado](#estado), [Próximo trabajo](#próximo-trabajo), [Referencias](#referencias).

## Base

Árbol temporal preparado desde main `{a.main}` y motor `{a.motor}`. No es un commit de merge ni autorización para fusionar. Codex trabaja en codex/motor; el integrador humano decide main. No crear worktrees ni hacer push.

Resolución de este documento: gana la estructura y relevo actualizado de Codex (1ebfb40), conservando la corrección de finos 2507edf. Se incorporan los hechos posteriores de main: imagen→JEF de referencia, cancelación y variantes SVG corregidas. Se descartan las afirmaciones históricas de que kmeans sigue experimental o de que el motor continúa idéntico a 4a7fd6b.

## Estado

- E1 v4: paleta refinada, color mediano, cobertura y medición de finos con exterior cero/kernel par. No borra ni engrosa para aprobar; 0,4 mm sigue provisional.
- Imagen→JEF funciona con parámetros de referencia y avisos; termina needs_review. GO independiente 014e368 y corrección SVG 29f73a8+25370ff. Nunca equivale a calibración física ni ready_for_sewout.
- Helper image_input.py: PNG/JPEG, 10 MiB/4 Mpx, EXIF visual normalizado y PNG de análisis sin pérdida. Test antes huérfano ya está versionado y pasa.
- Consumo API del helper todavía pendiente de Claude: límites del catálogo, dimensiones visuales de SourceAsset y PNG orientado para proveedor. No afirmar que esté conectado por existir el helper.
- Evidencias de auditoría independent-review/ son artefactos locales deliberados; los JEF y capturas no se incluyen en el commit del helper.

## Próximo trabajo

Claude mantiene API/web/F. Codex mantiene E/adaptador/pruebas. Correcciones de revisiones van después de variantes. La integración real de este árbol y cualquier calibración requieren su validación propia. La muestra H3 preparada se mide con David; coser por sí solo no habilita readiness digital.

## Referencias

- [Entrada orientada](IMAGE_INPUT.md) · [Reglas](ESTADO_Y_REGLAS.md) · [Coordinación](COORDINACION.md)
- [Protocolo H3](../../../tests/calibration/h3/PROTOCOLO_H3.md)
'''
(out/'CONTINUAR.resolved.md').write_text(resolved,encoding='utf8')
env=dict(os.environ,GIT_INDEX_FILE=str(index))
git('read-tree',tree,env=env)
blob=git('hash-object','-w','--stdin',data=resolved.encode()).strip()
git('update-index','--add','--cacheinfo',f'100644,{blob},{path}',env=env)
final_tree=git('write-tree',env=env).strip()
archive=out/'source.zip'
git('archive','--format=zip',f'--output={archive}',final_tree)
with zipfile.ZipFile(archive) as z: z.extractall(out/'source')
after={ref:git('log','-1','--format=%H',ref).strip() for ref in before}
assert before==after, 'A ref changed during preparation'
after_index_sha=hashlib.sha256(index_path.read_bytes()).hexdigest() if index_path.exists() else None
assert index_sha==after_index_sha, 'Actual index changed'
report={'main':a.main,'motor':a.motor,'merge_tree_initial':tree,'resolved_tree':final_tree,
        'conflicts':conflicts,'resolution':'Codex structure/current review wins; add newer main pipeline facts and helper handoff',
        'refs_before':before,'refs_after':after,'actual_index_unchanged':index_sha==after_index_sha,
        'commands':commands,'no_worktree_created':True,'no_ref_merge_performed':True}
(out/'preparation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
