"""Fail-closed OS memory limit for the disposable PDF parser process."""

import ctypes
import sys


PDF_MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
_job_handle = None


def _limit_windows(limit_bytes: int) -> None:
    from ctypes import wintypes

    class BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimit),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError("PDF memory job creation failed")
    try:
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x00000100
        limits.ProcessMemoryLimit = limit_bytes
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits),
                                               ctypes.sizeof(limits)):
            raise OSError("PDF memory job configuration failed")
        if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
            raise OSError("PDF memory job assignment failed")
    except BaseException:
        kernel.CloseHandle(job)
        raise
    global _job_handle
    _job_handle = job


def _limit_linux(limit_bytes: int) -> None:
    import resource

    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    target = min(limit_bytes, hard) if hard != resource.RLIM_INFINITY else limit_bytes
    if target <= 0:
        raise OSError("PDF address-space limit unavailable")
    resource.setrlimit(resource.RLIMIT_AS, (target, target))


def apply_pdf_memory_limit(limit_bytes: int = PDF_MEMORY_LIMIT_BYTES) -> None:
    if type(limit_bytes) is not int or limit_bytes < 1:
        raise ValueError("invalid PDF memory limit")
    if sys.platform == "win32":
        _limit_windows(limit_bytes)
    elif sys.platform.startswith("linux"):
        _limit_linux(limit_bytes)
    else:
        raise OSError("unsupported PDF memory limit platform")
