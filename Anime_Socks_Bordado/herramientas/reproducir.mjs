// Flujo local reproducible; usa temporales para evitar escrituras de Python en
// carpetas protegidas por Windows. No cambia ajustes de seguridad ni instalaciones.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const run=promisify(execFile);
const here=path.dirname(fileURLToPath(import.meta.url));
const target=path.dirname(here);
const python=process.env.ANIME_PYTHON||'C:/Users/david/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const work=await fs.mkdtemp(path.join(os.tmpdir(),'anime-socks-'));
const vendor=path.join(work,'vendor');
console.log('Trabajo temporal:',work);
await run(python,['-m','pip','install','--target',vendor,'--no-deps','pyembroidery==1.5.1','--disable-pip-version-check'],{maxBuffer:8e6});
for(const [script,argv] of [
  ['digitalizar.py',['--referencia',path.join(target,'trabajo','Referencia.png'),'--salida',work,'--escala-fisica','1.00134']],
  ['reparar_rellenos.py',['--salida',work]],
  ['exportar_validar.py',['--salida',work,'--vendor',vendor,'--solo','todos']],
  ['auditar.py',['--salida',work,'--vendor',vendor]],
  ['informe.py',['--salida',work]]
]){
  console.log(script);
  const result=await run(python,[path.join(here,script),...argv],{maxBuffer:16e6,timeout:600000});
  console.log(result.stdout);
}
for(const entry of await fs.readdir(work,{withFileTypes:true})){
  if(entry.name==='vendor')continue;
  await fs.cp(path.join(work,entry.name),path.join(target,entry.name),{recursive:true,force:true});
}
console.log('Resultados guardados:',target);
