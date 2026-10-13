"""Noninteractive uninstall cleanup. Exit nonzero rather than leave blocking behind."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import time
from app_signals import send_signal
from core import HostsFile


def wait_for_apps(kernel, timeout=30):
    """Hold both mutex handles through cleanup; never terminate an app forcibly."""
    deadline = time.monotonic() + timeout
    while True:
        handles = []
        running = []
        for demo in (False, True):
            handle = kernel.CreateMutexW(None, False, "Global\\FocusHarbor" + ("Preview" if demo else ""))
            if not handle:
                for held in handles:
                    kernel.CloseHandle(held)
                return []
            handles.append(handle)
            if ctypes.get_last_error() == 183:
                running.append(demo)
        if not running:
            return handles
        for handle in handles:
            kernel.CloseHandle(handle)
        if time.monotonic() >= deadline or not all(send_signal("quit", demo) for demo in running):
            return []
        time.sleep(.2)


def run():
    if os.name != "nt" or not ctypes.windll.shell32.IsUserAnAdmin():
        return 5
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handles = wait_for_apps(kernel)
    if not handles:
        return 2
    try:
        windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        backup = Path(os.environ["LOCALAPPDATA"]) / "FocusHarbor" / "hosts-before-uninstall.bak"
        changed = HostsFile(windows / "System32/drivers/etc/hosts", backup).apply([])
        if changed:
            try:
                subprocess.run([str(windows / "System32/ipconfig.exe"), "/flushdns"],
                               capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            except (OSError, subprocess.TimeoutExpired):
                pass  # Hosts restoration succeeded; browser caches may need a restart.
        return 0
    except (OSError, ValueError):
        return 1
    finally:
        for handle in handles:
            kernel.CloseHandle(handle)
