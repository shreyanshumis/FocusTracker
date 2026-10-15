import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from core import (START, END, HostsFile, decision, defaults, domain, expand_domains,
                  load_config, next_transition, render_hosts, save_config, schedule_active, validate)
from core import hard_block_domains, is_youtube, browser_policy


class DomainTests(unittest.TestCase):
    def test_empty_list_stays_empty_in_every_blocking_mode(self):
        for mode in ("auto", "blocked", "open"):
            c = defaults()
            c["mode"] = mode
            policy = browser_policy(c, datetime.now())
            self.assertEqual(policy["blockedDomains"], [])
            self.assertFalse(policy["youtubePrompt"])
            self.assertEqual(expand_domains(c["domains"]), [])

    def test_new_list_empty_and_user_links_cover_whole_site(self):
        c = defaults()
        self.assertEqual(c["domains"], [])
        for value in ("reddit.com", "www.reddit.com", "https://www.reddit.com/", "https://www.reddit.com/r/study/?sort=new#top"):
            self.assertEqual(domain(value), "reddit.com")
        c.update(mode="blocked", domains=["https://www.reddit.com/r/study/", "reddit.com"])
        validate(c)
        self.assertEqual(c["domains"], ["reddit.com"])
        self.assertEqual(browser_policy(c, datetime.now())["blockedDomains"], ["reddit.com"])
        self.assertEqual(expand_domains(c["domains"]), ["reddit.com", "www.reddit.com"])
        c["domains"] = []
        self.assertEqual(browser_policy(c, datetime.now())["blockedDomains"], [])

    def test_saved_user_list_survives_upgrade_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            self.assertEqual(load_config(path)["domains"], [])
            c = defaults()
            c["domains"] = ["example.com"]
            save_config(path, c)
            self.assertEqual(load_config(path)["domains"], ["example.com"])
            c["domains"] = []
            save_config(path, c)
            self.assertEqual(load_config(path)["domains"], [])

    def test_browser_policy_normalizes_www_and_respects_unblock(self):
        c = defaults()
        c.update(mode="blocked", domains=["www.conflictnations.com", "youtube.com"])
        policy = browser_policy(c, datetime(2026, 10, 2))
        self.assertEqual(policy["blockedDomains"], ["conflictnations.com"])
        self.assertTrue(policy["youtubePrompt"])
        c["mode"] = "open"
        policy = browser_policy(c, datetime(2026, 10, 2))
        self.assertEqual(policy["blockedDomains"], [])
        self.assertFalse(policy["youtubePrompt"])
    def test_youtube_is_prompt_only(self):
        self.assertEqual(hard_block_domains(["youtube.com", "m.youtube.com", "youtu.be", "reddit.com"]), ["reddit.com"])
        self.assertTrue(is_youtube("www.youtube-nocookie.com"))
        self.assertFalse(is_youtube("notyoutube.com"))
        self.assertFalse(is_youtube("youtube.com.evil.com"))

    def test_upgrade_removes_old_youtube_hosts_rules(self):
        old = render_hosts(b"# original\n", ["youtube.com", "reddit.com"])
        new = render_hosts(old, hard_block_domains(["youtube.com", "reddit.com"]))
        self.assertNotIn(b"youtube.com", new)
        self.assertIn(b"reddit.com", new)

    def test_urls_and_international_names(self):
        self.assertEqual(domain(" HTTPS://YouTube.com/watch?v=1 "), "youtube.com")
        self.assertEqual(domain("bücher.de"), "xn--bcher-kva.de")

    def test_rejects_injection_and_non_domains(self):
        for value in ["localhost", "127.0.0.1", "*.reddit.com", "x.com\n0.0.0.0 evil.com", "bad domain.com", "https://me:secret@example.com", "example.com:80", "-bad.com", "ftp://example.com", "a.local", "a.com#\nentry"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                domain(value)

    def test_www_and_dedup(self):
        self.assertEqual(expand_domains(["youtube.com", "www.youtube.com"]), ["www.youtube.com", "youtube.com"])


class ScheduleTests(unittest.TestCase):
    def rule(self, **kw):
        return {"name": "Work", "days": [0, 1, 2, 3, 4], "start": "09:00", "end": "17:00", "enabled": True, **kw}

    def test_exact_boundaries(self):
        rule = self.rule()
        for hour, minute, active in [(8, 59, False), (9, 0, True), (16, 59, True), (17, 0, False)]:
            self.assertEqual(schedule_active(rule, datetime(2026, 10, 5, hour, minute)), active)
        self.assertFalse(schedule_active(rule, datetime(2026, 10, 10, 10)))

    def test_overnight_uses_start_day(self):
        rule = self.rule(days=[4], start="22:00", end="07:00")
        self.assertTrue(schedule_active(rule, datetime(2026, 10, 9, 23)))
        self.assertTrue(schedule_active(rule, datetime(2026, 10, 10, 6, 59)))
        self.assertFalse(schedule_active(rule, datetime(2026, 10, 10, 7)))
        self.assertFalse(schedule_active(rule, datetime(2026, 10, 9, 6)))

    def test_sunday_to_monday(self):
        self.assertTrue(schedule_active(self.rule(days=[6], start="22:00", end="07:00"), datetime(2026, 10, 5, 1)))

    def test_disabled_schedule(self):
        self.assertFalse(schedule_active(self.rule(enabled=False), datetime(2026, 10, 5, 10)))

    def test_overlap_and_manual_override(self):
        c = defaults()
        c["schedules"] = [self.rule(), self.rule(name="Evening", start="16:00", end="19:00")]
        self.assertTrue(decision(c, datetime(2026, 10, 5, 18))[0])
        self.assertFalse(decision(c, datetime(2026, 10, 5, 19))[0])
        c["mode"] = "open"
        self.assertFalse(decision(c, datetime(2026, 10, 5, 10))[0])
        c["mode"] = "blocked"
        self.assertTrue(decision(c, datetime(2026, 10, 10, 23))[0])

    def test_timer_expiry_restores_mode_including_after_sleep(self):
        now = datetime(2026, 10, 5, 10)
        c = defaults()
        c["mode"] = "blocked"
        c["timer"] = {"block": False, "until": now.timestamp() + 60}
        self.assertFalse(decision(c, now)[0])
        self.assertTrue(decision(c, datetime(2026, 10, 5, 10, 1))[0])
        self.assertTrue(decision(c, datetime(2026, 10, 5, 12))[0])

    def test_focus_timer_overrides_auto_then_restores_schedule(self):
        c = defaults()
        now = datetime(2026, 10, 5, 8, 30)
        c["timer"] = {"block": True, "until": now.timestamp() + 60}
        self.assertTrue(decision(c, now)[0])
        self.assertFalse(decision(c, datetime(2026, 10, 5, 8, 31))[0])

    def test_next_transition(self):
        c = defaults()
        c["schedules"] = [self.rule()]
        self.assertEqual(next_transition(c, datetime(2026, 10, 5, 8)), datetime(2026, 10, 5, 9))


class HostsTests(unittest.TestCase):
    def test_round_trip_preserves_custom_bytes_and_crlf(self):
        original = b"# Existing custom file\r\n127.0.0.1 localhost\r\n192.168.1.2 myserver\r\n"
        blocked = render_hosts(original, ["youtube.com"])
        self.assertTrue(blocked.startswith(original))
        self.assertIn(b"0.0.0.0 youtube.com\r\n", blocked)
        self.assertIn(b":: www.youtube.com\r\n", blocked)
        self.assertEqual(render_hosts(blocked, []), original)

    def test_preserves_entries_added_after_block(self):
        blocked = render_hosts(b"# comment\n", ["youtube.com"])
        edited = blocked + b"127.0.0.1 other.local\n"
        self.assertEqual(render_hosts(edited, []), b"# comment\n127.0.0.1 other.local\n")

    def test_idempotent_and_replace(self):
        first = render_hosts(b"", ["reddit.com"])
        self.assertEqual(render_hosts(first, ["reddit.com"]), first)
        second = render_hosts(first, ["youtube.com"])
        self.assertNotIn(b"reddit.com", second)
        self.assertEqual(second.count(START), 1)

    def test_malformed_markers_fail_closed_without_editing(self):
        for data in [START + b"\n", END + b"\n", START+b"\n"+START+b"\n"+END+b"\n", START+b"\n"+END+b"\n"+END+b"\n"]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                render_hosts(data, [])

    def test_no_trailing_newline_and_bom(self):
        original = b"\xef\xbb\xbf# Existing UTF-8 comment"
        self.assertEqual(render_hosts(render_hosts(original, ["reddit.com"]), []), original + b"\n")

    def test_reject_utf16(self):
        with self.assertRaises(ValueError):
            render_hosts("127.0.0.1 localhost".encode("utf-16"), [])

    def test_real_file_round_trip_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path, backup = Path(folder) / "hosts", Path(folder) / "backup"
            original = b"127.0.0.1 localhost\r\n"
            path.write_bytes(original)
            hosts = HostsFile(path, backup)
            self.assertTrue(hosts.apply(["youtube.com"]))
            self.assertEqual(backup.read_bytes(), original)
            self.assertFalse(hosts.apply(["youtube.com"]))
            self.assertTrue(hosts.apply([]))
            self.assertEqual(path.read_bytes(), original)


class SettingsTests(unittest.TestCase):
    def test_round_trip_with_timer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            c = defaults()
            c["timer"] = {"block": True, "until": datetime(2026, 10, 5).timestamp()}
            save_config(path, c)
            self.assertEqual(load_config(path), c)

    def test_corrupt_settings_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("invalid json")
            with self.assertRaises(ValueError):
                load_config(path)
            self.assertEqual(path.read_text(), "invalid json")

    def test_reject_invalid_schedule(self):
        for rule in [dict(name="x", start="09:00", end="09:00", days=[0]), dict(name="x", start="9am", end="17:00", days=[0]), dict(name="x", start="09:00", end="17:00", days=[])]:
            c = defaults()
            c["schedules"] = [rule]
            with self.assertRaises(ValueError):
                validate(c)


if __name__ == "__main__":
    unittest.main()
