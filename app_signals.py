"""Windows events for reopening the tray app and requesting a safe exit."""
import ctypes
from ctypes import wintypes


def api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenEventW.restype = wintypes.HANDLE
    kernel.SetEvent.argtypes = [wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel


def event_name(action, demo=False):
    return "Global\\FocusHarbor" + ("Preview" if demo else "") + "-" + action


def send_signal(action, demo=False):
    kernel = api()
    handle = kernel.OpenEventW(0x0002, False, event_name(action, demo))
    if not handle:
        return False
    try:
        return bool(kernel.SetEvent(handle))
    finally:
        kernel.CloseHandle(handle)


class AppSignals:
    def __init__(self, demo=False):
        self.kernel = api()
        self.handles = {}
        for action in ("show", "quit"):
            handle = self.kernel.CreateEventW(None, False, False, event_name(action, demo))
            if not handle:
                self.close()
                raise ctypes.WinError(ctypes.get_last_error())
            self.handles[action] = handle

    def pending(self):
        return [action for action, handle in self.handles.items()
                if self.kernel.WaitForSingleObject(handle, 0) == 0]

    def close(self):
        for handle in self.handles.values():
            self.kernel.CloseHandle(handle)
        self.handles.clear()
