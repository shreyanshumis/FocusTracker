import os
import unittest
import uuid
from unittest.mock import patch
import app_signals


@unittest.skipUnless(os.name == "nt", "Windows app events")
class SignalTests(unittest.TestCase):
    def test_show_and_quit_are_consumed_once_and_handles_close(self):
        prefix = "Local\\FocusTracker-test-" + uuid.uuid4().hex
        with patch.object(app_signals, "event_name", side_effect=lambda action, demo=False: prefix + action):
            self.assertFalse(app_signals.send_signal("show"))
            signals = app_signals.AppSignals()
            try:
                self.assertTrue(app_signals.send_signal("show"))
                self.assertEqual(signals.pending(), ["show"])
                self.assertEqual(signals.pending(), [])
                self.assertTrue(app_signals.send_signal("quit"))
                self.assertEqual(signals.pending(), ["quit"])
            finally:
                signals.close()
            self.assertFalse(app_signals.send_signal("quit"))
