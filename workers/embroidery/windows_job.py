"""Windows process-tree lifetime without taskkill, services or admin privileges."""
import ctypes as C
from ctypes import wintypes as W

KILL_ON_JOB_CLOSE = 0x2000
EXTENDED_LIMIT_INFORMATION = 9
BASIC_ACCOUNTING_INFORMATION = 1
CREATE_SUSPENDED = 0x00000004
SNAP_THREADS = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002


class ThreadEntry(C.Structure):
    _fields_ = [("size", W.DWORD), ("usage", W.DWORD), ("thread_id", W.DWORD),
                ("process_id", W.DWORD), ("base_priority", W.LONG),
                ("delta_priority", W.LONG), ("flags", W.DWORD)]


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong),
                ("flags", W.DWORD), ("min_working_set", C.c_size_t),
                ("max_working_set", C.c_size_t), ("active_limit", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class IoCounters(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IoCounters),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [("user_time", C.c_longlong), ("kernel_time", C.c_longlong),
                ("period_user", C.c_longlong), ("period_kernel", C.c_longlong),
                ("page_faults", W.DWORD), ("total", W.DWORD),
                ("active", W.DWORD), ("terminated", W.DWORD)]


class WindowsJob:
    def __init__(self, process):
        self.api = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
            "CloseHandle": ([W.HANDLE], W.BOOL),
            "CreateToolhelp32Snapshot": ([W.DWORD, W.DWORD], W.HANDLE),
            "Thread32First": ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            "Thread32Next": ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            "OpenThread": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            "ResumeThread": ([W.HANDLE], W.DWORD),
        }
        for name, (arguments, result) in signatures.items():
            getattr(self.api, name).argtypes, getattr(self.api, name).restype = arguments, result
        self.handle = self.api.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.basic.flags = KILL_ON_JOB_CLOSE
        try:
            if not self.handle:
                raise C.WinError(C.get_last_error())
            self._check(self.api.SetInformationJobObject(self.handle, EXTENDED_LIMIT_INFORMATION, C.byref(limits), C.sizeof(limits)))
            self._check(self.api.AssignProcessToJobObject(self.handle, int(process._handle)))
        except OSError:
            self.close()
            process.kill()
            process.wait(timeout=15)
            raise

    @staticmethod
    def _check(result):
        if not result:
            raise C.WinError(C.get_last_error())

    def terminate(self, process):
        self._check(self.api.TerminateJobObject(self.handle, 1))
        process.wait(timeout=15)
        accounting = Accounting()
        self._check(self.api.QueryInformationJobObject(self.handle, BASIC_ACCOUNTING_INFORMATION, C.byref(accounting), C.sizeof(accounting), None))
        return {"method": "TerminateJobObject", "active_processes": accounting.active,
                "total_processes": accounting.total, "confirmed": accounting.active == 0}

    def resume(self, process_id):
        snapshot = self.api.CreateToolhelp32Snapshot(SNAP_THREADS, 0)
        if snapshot == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        entry = ThreadEntry()
        entry.size = C.sizeof(entry)
        try:
            more = self.api.Thread32First(snapshot, C.byref(entry))
            while more:
                if entry.process_id == process_id:
                    self._resume_thread(entry.thread_id)
                    return
                more = self.api.Thread32Next(snapshot, C.byref(entry))
            raise ProcessLookupError("Suspended initial thread was not found")
        finally:
            self.api.CloseHandle(snapshot)

    def _resume_thread(self, thread_id):
        thread = self.api.OpenThread(THREAD_SUSPEND_RESUME, False, thread_id)
        self._check(thread)
        try:
            if self.api.ResumeThread(thread) != 1:
                raise OSError("Expected exactly one suspension on initial thread")
        finally:
            self.api.CloseHandle(thread)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
