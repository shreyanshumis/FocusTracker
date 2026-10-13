import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import installer_cleanup
from core import render_hosts, START


@unittest.skipUnless(os.name == "nt", "Windows uninstall helper")
class UninstallCleanupTests(unittest.TestCase):
    def exercise(self, content, last_error=0):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            hosts = root / "System32/drivers/etc/hosts"
            hosts.parent.mkdir(parents=True)
            hosts.write_bytes(content)
            kernel = Mock()
            kernel.CreateMutexW.return_value = 123
            with patch.dict(os.environ, {"SystemRoot": str(root), "LOCALAPPDATA": str(root / "data")}), \
                 patch.object(installer_cleanup.ctypes.windll.shell32, "IsUserAnAdmin", return_value=True), \
                 patch.object(installer_cleanup.ctypes, "WinDLL", return_value=kernel), \
                 patch.object(installer_cleanup.ctypes, "get_last_error", return_value=last_error), \
                 patch.object(installer_cleanup, "send_signal", return_value=False), \
                 patch.object(installer_cleanup.subprocess, "run"):
                result = installer_cleanup.run()
            return result, hosts.read_bytes()

    def test_removes_only_managed_rules(self):
        original = b"127.0.0.1 localhost\r\n192.168.1.2 custom.local\r\n"
        result, output = self.exercise(render_hosts(original, ["reddit.com"]))
        self.assertEqual(result, 0)
        self.assertEqual(output, original)

    def test_refuses_when_app_is_running(self):
        blocked = render_hosts(b"", ["reddit.com"])
        result, output = self.exercise(blocked, last_error=183)
        self.assertEqual(result, 2)
        self.assertEqual(output, blocked)

    def test_malformed_rules_abort_uninstall(self):
        original = START + b"\r\n"
        result, output = self.exercise(original)
        self.assertEqual(result, 1)
        self.assertEqual(output, original)

    def test_unblocked_hosts_unchanged(self):
        original = b"127.0.0.1 localhost\r\n"
        result, output = self.exercise(original)
        self.assertEqual((result, output), (0, original))

    def test_running_app_exits_before_cleanup_acquires_mutexes(self):
        kernel = Mock()
        kernel.CreateMutexW.side_effect = [1, 2, 3, 4]
        with patch.object(installer_cleanup.ctypes, "get_last_error", side_effect=[183, 0, 0, 0]), \
             patch.object(installer_cleanup, "send_signal", return_value=True) as signal, \
             patch.object(installer_cleanup.time, "sleep"):
            handles = installer_cleanup.wait_for_apps(kernel)
        self.assertEqual(handles, [3, 4])
        signal.assert_called_once_with("quit", False)
        self.assertEqual(kernel.CloseHandle.call_count, 2)

    def test_unresponsive_app_aborts_without_force_termination(self):
        kernel = Mock()
        kernel.CreateMutexW.side_effect = [1, 2]
        with patch.object(installer_cleanup.ctypes, "get_last_error", return_value=183), \
             patch.object(installer_cleanup, "send_signal") as signal:
            self.assertEqual(installer_cleanup.wait_for_apps(kernel, timeout=0), [])
        signal.assert_not_called()
        self.assertEqual(kernel.CloseHandle.call_count, 2)
