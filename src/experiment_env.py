"""Honest local experiment metadata; no network or machine-wide configuration.

Linux remains the resource-enforced default. Portable execution requires an
explicit runner opt-in and never claims Linux limits or RSS on another OS.
"""
import ctypes
import os
import platform
import sys


def configure(cpu_soft=35, cpu_hard=40):
    if sys.platform.startswith('linux'):
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_soft, cpu_hard))
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
        return {'mode': 'linux-enforced', 'affinity': sorted(os.sched_getaffinity(0)),
                'address_space_limit_bytes': 3 * 1024**3,
                'cpu_limit_seconds': [cpu_soft, cpu_hard]}
    if os.environ.get('CALENDARISO_PORTABLE') != '1':
        raise RuntimeError('Linux limits unavailable; use reproduce.py --portable explicitly.')
    affinity = pin_current_process()
    return {'mode': 'portable-explicit', 'affinity': affinity,
            'address_space_limit_bytes': None, 'cpu_limit_seconds': None}


def pin_current_process():
    """Pin only this owned process, checking the actual native API outcome."""
    if sys.platform == 'win32':
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.GetCurrentProcess.restype = wintypes.HANDLE
        api.GetProcessAffinityMask.argtypes = [wintypes.HANDLE,
                                               ctypes.POINTER(ctypes.c_size_t),
                                               ctypes.POINTER(ctypes.c_size_t)]
        api.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        handle = api.GetCurrentProcess()
        process, system = ctypes.c_size_t(), ctypes.c_size_t()
        if not api.GetProcessAffinityMask(handle, ctypes.byref(process), ctypes.byref(system)):
            raise OSError(ctypes.get_last_error(), 'GetProcessAffinityMask failed')
        chosen = process.value & -process.value
        if not chosen or not api.SetProcessAffinityMask(handle, chosen):
            raise OSError(ctypes.get_last_error(), 'SetProcessAffinityMask failed')
        if not api.GetProcessAffinityMask(handle, ctypes.byref(process), ctypes.byref(system)):
            raise OSError(ctypes.get_last_error(), 'affinity verification failed')
        if process.value != chosen:
            raise RuntimeError('native affinity does not match requested eligible CPU')
        return {'windows_process_mask': process.value}
    if hasattr(os, 'sched_getaffinity'):
        cpu = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {cpu})
        return {'linux_cpus': sorted(os.sched_getaffinity(0))}
    return {'status': 'unsupported-unpinned'}


def peak_rss_kib():
    if sys.platform.startswith('linux'):
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return None


def environment():
    return {'python': sys.version, 'platform': platform.platform(),
            'processor': platform.processor(), 'optimize': sys.flags.optimize,
            'timers': ['perf_counter_ns', 'process_time_ns']}
