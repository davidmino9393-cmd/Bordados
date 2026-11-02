"""Bounded subprocesses with binary logs and no interactive standard input."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class WorkerFailure(Exception):
    def __init__(self, code, reason, evidence):
        super().__init__(reason)
        self.issue = {"code": code, "reason": reason, "evidence": evidence}


def stop_tree(process, job=None):
    if os.name == "nt":
        return job.terminate(process)
    else:
        os.killpg(process.pid, signal.SIGKILL)
        result = {"method": "killpg SIGKILL"}
    process.wait(timeout=15)
    return result


def run_logged(command, directory, name, timeout, cancel_event=None, env_overrides=None):
    directory = Path(directory)
    record = {"command": list(map(str, command)), "timeout_s": timeout,
              "stdin": "DEVNULL", "shell": False, "hidden_window": os.name == "nt"}
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    if os.name == "nt":
        from windows_job import CREATE_SUSPENDED
        options["creationflags"] |= CREATE_SUSPENDED
        record["started_suspended"] = True
    env = dict(os.environ, INKSTITCH_OFFLINE_SCRIPT="true", PYTHONUTF8="1", LANGUAGE="en_US")
    if env_overrides:
        env.update(env_overrides)
    for key in ("DISPLAY", "WAYLAND_DISPLAY", "PYTHONIOENCODING"):
        env.pop(key, None)
    started, job = time.monotonic(), None
    with (directory / f"{name}.stdout.bin").open("wb") as stdout, (directory / f"{name}.stderr.txt").open("wb") as stderr:
        try:
            process = subprocess.Popen(command, cwd=directory, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, env=env, **options)
            record["pid"] = process.pid
            if os.name == "nt":
                from windows_job import WindowsJob
                job = WindowsJob(process)
                record["process_tree_control"] = "Windows Job Object, KILL_ON_JOB_CLOSE"
                job.resume(process.pid)
            if cancel_event is None:
                process.wait(timeout=timeout)
            else:
                while process.poll() is None:
                    if cancel_event.is_set():
                        record["cancelled"] = True
                        record["cleanup"] = stop_tree(process, job)
                        break
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    try:
                        process.wait(timeout=min(0.1, remaining))
                    except subprocess.TimeoutExpired:
                        pass
            record["returncode"] = process.returncode
        except subprocess.TimeoutExpired:
            record["timed_out"] = True
            record["cleanup"] = stop_tree(process, job)
        except OSError as exc:
            record["spawn_error"] = str(exc)
            if "pid" in record and process.poll() is None:
                process.kill()
                process.wait(timeout=15)
                record["startup_parent_terminated"] = True
        finally:
            if job is not None:
                job.close()
            record["duration_ms"] = round((time.monotonic() - started) * 1000)
            (directory / f"{name}.process.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if "spawn_error" in record:
        reason = "process_control_error" if "pid" in record else "binary_not_found_or_not_executable"
        raise WorkerFailure("WORKER_EXPORT_FAILED", reason, record)
    if record.get("timed_out"):
        raise WorkerFailure("WORKER_TIMEOUT", "process_deadline_exceeded", record)
    if record.get("cancelled"):
        raise WorkerFailure("JOB_CANCELLED", "process_tree_stopped", record)
    payload = (directory / f"{name}.stdout.bin").read_bytes()
    if record["returncode"] != 0 or not payload:
        raise WorkerFailure("WORKER_EXPORT_FAILED", "nonzero_exit_or_empty_payload", record)
    return payload, record
