"""Measure real E1 at 20 MP in isolated children, without changing production limits.

Run with the project's Python: python -B tests/engine/evidence/image-input/benchmark_20mp.py
Only the child process overrides image_input.MAX_INPUT_PIXELS, in memory. Its byte
limit, geometry limits, segmentation algorithm and output precision are unchanged.
"""
import argparse
import ctypes
from ctypes import wintypes
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
PIXELS = 20_000_000
SIZE = (4000, 5000)
MIB = 1024 * 1024
HARD_CHILD_COMMIT_BYTES = int(1.5 * 1024 ** 3)
MIN_FREE_BYTES = int(1.5 * 1024 ** 3)
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100


class MemoryStatus(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in (
            'total_physical', 'available_physical', 'total_pagefile', 'available_pagefile',
            'total_virtual', 'available_virtual', 'available_extended')]


class ProcessMemory(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'peak_working_set', 'working_set', 'peak_paged_pool', 'paged_pool',
            'peak_nonpaged_pool', 'nonpaged_pool', 'pagefile', 'peak_pagefile', 'private')]


def physical_memory():
    result = MemoryStatus()
    result.length = ctypes.sizeof(result)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(result)):
        raise ctypes.WinError()
    return {'total_bytes': result.total_physical, 'available_bytes': result.available_physical}


def process_memory(handle):
    result = ProcessMemory()
    result.cb = ctypes.sizeof(result)
    api = ctypes.windll.psapi.GetProcessMemoryInfo
    api.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    if not api(handle, ctypes.byref(result), result.cb):
        raise ctypes.WinError()
    return {name: getattr(result, name) for name in
            ('peak_working_set', 'working_set', 'peak_pagefile', 'private')}


def current_memory():
    get = ctypes.windll.kernel32.GetCurrentProcess
    get.restype = wintypes.HANDLE
    return process_memory(get())


def prepare_fixtures(directory):
    from PIL import Image, ImageDraw, ImageOps
    directory.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGB', SIZE, 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((250, 250, 3750, 4750), fill='#153C78')
    draw.ellipse((1100, 1300, 2900, 3700), fill='white')
    draw.rectangle((1450, 1700, 2550, 3300), fill='#E88424')
    draw.ellipse((1750, 2200, 2250, 2800), fill='#36A160')
    image.save(directory / 'synthetic.png')
    image.close()
    with Image.open(ROOT / 'tests/fixtures/h2/Anime_Socks.png') as original:
        fitted = ImageOps.contain(original.convert('RGB'), SIZE, Image.Resampling.LANCZOS)
        image = Image.new('RGB', SIZE, 'white')
        image.paste(fitted, ((SIZE[0]-fitted.width)//2, (SIZE[1]-fitted.height)//2))
        image.save(directory / 'reference.png')
        fitted.close()
        image.close()
    gc.collect()
    return [directory / 'synthetic.png', directory / 'reference.png']


def child(args):
    sys.path[:0] = [str(ROOT/'packages/contracts'), str(ROOT/'workers/embroidery')]
    from PIL import Image, __version__ as pillow_version
    from embroidery_contracts import JobSettings, SourceAsset
    from vectorize import vectorize, VectorizeFailure
    from vectorize import image_input
    data = args.input.read_bytes()
    with Image.open(args.input) as image:
        size = image.size
    assert size[0]*size[1] == PIXELS
    assert len(data) <= image_input.MAX_INPUT_BYTES
    original_limit = image_input.MAX_INPUT_PIXELS
    image_input.MAX_INPUT_PIXELS = PIXELS  # this child only; no source/config change
    settings = json.loads((ROOT/'packages/contracts/fixtures/generation-from-svg.json').read_text())['payload']['settings']
    settings.update(target={'width_mm':150,'height_mm':150,'fit':'contain'}, color_limit=3)
    digest = hashlib.sha256(data).hexdigest()
    asset = SourceAsset(asset_id='asset_benchmark', project_id='project_benchmark', sha256=digest,
                        media_type='image/png', original_filename=args.input.name,
                        original_width_px=size[0], original_height_px=size[1])
    record = {'case':args.input.stem,'size':size,'pixels':PIXELS,'encoded_bytes':len(data),
              'input_sha256':digest,'original_production_pixel_limit':original_limit,
              'benchmark_only_pixel_limit':image_input.MAX_INPUT_PIXELS,
              'byte_limit_unchanged':image_input.MAX_INPUT_BYTES,'python':sys.version,'pillow':pillow_version}
    started = time.perf_counter()
    try:
        result = vectorize(data,'image/png',asset,None,JobSettings.model_validate(settings),
                           job_id='job_benchmark',revision_id='rev_benchmark')
        record.update(status='passed',duration_s=time.perf_counter()-started,
                      vectorize_duration_ms=result.duration_ms, objects=len(result.document.objects),
                      editable_svg_bytes=len(result.editable_svg),
                      issues=[issue.code.value for issue in result.issues])
    except VectorizeFailure as failure:
        record.update(status='controlled_failure',duration_s=time.perf_counter()-started,
                      issue=failure.issue.model_dump(mode='json'))
    except Exception as exc:
        record.update(status='unexpected_failure',duration_s=time.perf_counter()-started,error=repr(exc))
    record['memory'] = current_memory()
    record['input_unchanged'] = hashlib.sha256(data).hexdigest()==digest
    args.output.write_text(json.dumps(record,indent=2),encoding='utf8')
    print(json.dumps(record),flush=True)


def measure(path, directory, timeout):
    sys.path.insert(0, str(ROOT / 'workers/embroidery'))
    from windows_job import WindowsJob, ExtendedLimits, CREATE_SUSPENDED, KILL_ON_JOB_CLOSE, EXTENDED_LIMIT_INFORMATION
    result_path = directory / f'{path.stem}-result.json'
    command = [sys.executable,'-B',str(Path(__file__).resolve()),'--child','--input',str(path),'--output',str(result_path)]
    started = time.monotonic()
    initial = physical_memory()
    if initial['available_bytes'] < MIN_FREE_BYTES:
        return {'case':path.stem,'status':'not_run_memory_safety','physical_before':initial}
    with (directory/f'{path.stem}.stdout.log').open('w') as stdout, (directory/f'{path.stem}.stderr.log').open('w') as stderr:
        process = subprocess.Popen(command,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW | CREATE_SUSPENDED,
                                   env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        job = WindowsJob(process)
        limits = ExtendedLimits()
        limits.basic.flags = KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_PROCESS_MEMORY
        limits.process_memory = HARD_CHILD_COMMIT_BYTES
        try:
            job._check(job.api.SetInformationJobObject(job.handle, EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)))
            job.resume(process.pid)
        except BaseException:
            job.close()
            process.wait(timeout=15)
            raise
        open_process = ctypes.windll.kernel32.OpenProcess
        open_process.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        open_process.restype=wintypes.HANDLE
        handle = open_process(0x0410,False,process.pid)
        if not handle:
            process.terminate(); process.wait()
            raise ctypes.WinError()
        peaks={'peak_working_set':0,'peak_pagefile':0,'private':0}
        minimum_free=initial['available_bytes']; stopped=None
        try:
            while process.poll() is None:
                physical = physical_memory()
                minimum_free=min(minimum_free,physical['available_bytes'])
                memory=process_memory(handle)
                for key in peaks: peaks[key]=max(peaks[key],memory[key])
                if physical['available_bytes'] < MIN_FREE_BYTES:
                    stopped='system_free_memory_below_1_5_GiB'
                if time.monotonic()-started > timeout:
                    stopped='process_deadline_exceeded'
                if stopped:
                    process.terminate(); process.wait(timeout=15); break
                time.sleep(.05)
        finally:
            ctypes.windll.kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
            ctypes.windll.kernel32.CloseHandle(handle)
            job.close()
        process.wait(timeout=15)
    record = json.loads(result_path.read_text()) if result_path.exists() else {'case':path.stem,'status':stopped or 'child_failed'}
    record.update(command=command,process_returncode=process.returncode,total_wall_s=time.monotonic()-started,
                  sampled_peaks=peaks,physical_before=initial,minimum_system_available_bytes=minimum_free,
                  timeout_s=timeout,stopped_reason=stopped,
                  hard_child_commit_limit_bytes=HARD_CHILD_COMMIT_BYTES,
                  minimum_free_memory_bytes=MIN_FREE_BYTES,
                  containment='Windows Job Object process memory limit set while suspended, before resume')
    return record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--child',action='store_true')
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'tests/engine/evidence/image-input/benchmark-20mp.json')
    parser.add_argument('--runtime',type=Path,default=ROOT/'tests/engine/.tmp/benchmark-20mp')
    parser.add_argument('--timeout',type=float,default=600)
    args=parser.parse_args()
    if args.child:
        child(args);return
    physical=physical_memory()
    prior=json.loads(args.output.read_text()) if args.output.exists() else {}
    report={'method':'isolated real E1 children; in-memory pixel-cap override only, no downscale during vectorize',
            'production_changed':False,'timeout_s':args.timeout,'physical_initial':physical,'cases':[],
            'preflight_entries':prior.get('preflight_entries',[]) + [c for c in prior.get('cases',[]) if c.get('status')=='not_run_memory_safety'],
            'guard_change_authorized_by_parent':'Hard 1.5 GiB child commit cap and 1.5 GiB free-RAM reserve; guard relaxed from preflight percentage only for bounded measurement, not production'}
    fixtures=prepare_fixtures(args.runtime)
    log=ROOT/'tests/engine/evidence/image-input/benchmark-20mp.log'
    log.write_text('20 MP E1 measurement; production unchanged\n',encoding='utf8')
    for path in fixtures:
        print('START',path.stem,flush=True)
        record=measure(path,args.runtime,args.timeout)
        report['cases'].append(record)
        args.output.write_text(json.dumps(report,indent=2),encoding='utf8')
        with log.open('a',encoding='utf8') as f: f.write(json.dumps(record)+'\n')
        print('RESULT',path.stem,record.get('status'),record.get('duration_s'),record.get('memory'),flush=True)
        if record.get('stopped_reason'): break
    report['all_cases_completed'] = len(report['cases'])==len(fixtures) and all(c.get('status')=='passed' for c in report['cases'])
    report['all_cases_finished_within_resource_budget'] = len(report['cases'])==len(fixtures) and all(
        c.get('process_returncode')==0 and c.get('stopped_reason') is None for c in report['cases'])
    report['all_inputs_vectorized_successfully'] = report['all_cases_completed']
    report['decision'] = 'measurement_only; parent/David decide production cap from observed results'
    args.output.write_text(json.dumps(report,indent=2),encoding='utf8')


if __name__=='__main__':
    main()
