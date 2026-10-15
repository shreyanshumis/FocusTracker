"""Pure scheduling and hosts-file logic. No system changes on import."""
from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

START = b"# BEGIN FOCUS HARBOR MANAGED BLOCK"
END = b"# END FOCUS HARBOR MANAGED BLOCK"



def is_youtube(name: str) -> bool:
    return any(name == base or name.endswith("." + base)
               for base in ("youtube.com", "youtu.be", "youtube-nocookie.com"))


def hard_block_domains(entries: list[str]) -> list[str]:
    """YouTube is handled by the study-check browser extension instead."""
    return [name for name in entries if not is_youtube(name)]


def browser_policy(config: dict, now: datetime) -> dict:
    active = decision(config, now)[0]
    return {"app": "FocusHarbor", "version": 2,
            "youtubePrompt": active and any(is_youtube(n) for n in config["domains"]),
            "blockedDomains": sorted({n[4:] if n.startswith("www.") else n
                                      for n in hard_block_domains(config["domains"])}) if active else []}


def domain(value: str) -> str:
    value = value.strip().lower()
    if not value or any(c.isspace() for c in value) or "*" in value:
        raise ValueError("Enter a website, such as example.com. Wildcards and spaces are not supported.")
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.port:
        raise ValueError("Use a website address without a port or login details.")
    name = (parsed.hostname or "").rstrip(".")
    try:
        name = name.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("That website name is not valid.") from exc
    try:
        ipaddress.ip_address(name)
    except ValueError:
        pass
    else:
        raise ValueError("Enter a website name, not an IP address.")
    labels = name.split(".")
    if len(name) > 253 or len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels):
        raise ValueError("Enter a valid website name, such as example.com.")
    if name.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Use a public website name, not a local network address.")
    return name[4:] if name.startswith("www.") else name


def expand_domains(entries: list[str]) -> list[str]:
    result = set()
    for entry in entries:
        name = domain(entry)
        result.add(name)
        # Include the common www alias, not arbitrary subdomains.
        result.add(name[4:] if name.startswith("www.") else "www." + name)
    return sorted(result)


def minutes(value: str) -> int:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Use a 24-hour time such as 09:00 or 17:30.")
    h, m = map(int, value.split(":"))
    return h * 60 + m


def schedule_active(rule: dict, now: datetime) -> bool:
    if not rule.get("enabled", True):
        return False
    start, end = minutes(rule["start"]), minutes(rule["end"])
    current = now.hour * 60 + now.minute
    days = rule["days"]
    if start < end:
        return now.weekday() in days and start <= current < end
    # Overnight periods belong to the day on which they begin.
    return (now.weekday() in days and current >= start) or ((now.weekday() - 1) % 7 in days and current < end)


def decision(config: dict, now: datetime) -> tuple[bool, str]:
    timer = config.get("timer")
    if type(config.get("reduced_motion", False)) is not bool:
        raise ValueError("Invalid motion preference.")
    if timer and now.timestamp() < timer["until"]:
        return timer["block"], "Focus timer" if timer["block"] else "Timed break"
    if config["mode"] == "blocked":
        return True, "Manual block"
    if config["mode"] == "open":
        return False, "Manual unblock"
    active = [r["name"] for r in config["schedules"] if schedule_active(r, now)]
    return bool(active), ", ".join(active) if active else "Outside scheduled hours"


def next_transition(config: dict, now: datetime) -> datetime | None:
    previous = decision(config, now)[0]
    timer = config.get("timer")
    if timer and timer["until"] > now.timestamp():
        expiry = datetime.fromtimestamp(timer["until"])
        if decision(config, expiry)[0] != previous:
            return expiry
    cursor = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(8 * 24 * 60):
        if decision(config, cursor)[0] != previous:
            return cursor
        cursor += timedelta(minutes=1)
    return None


def defaults() -> dict:
    return {"version": 1, "mode": "auto", "timer": None,
            "domains": [], "schedules": []}


def validate(config: dict) -> dict:
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("Unsupported settings format.")
    if config.get("mode") not in ("auto", "blocked", "open"):
        raise ValueError("Invalid blocking mode.")
    if not isinstance(config.get("domains"), list) or len(config["domains"]) > 500:
        raise ValueError("Website list must contain at most 500 entries.")
    config["domains"] = sorted({domain(x) for x in config["domains"]})
    schedules = config.get("schedules")
    if not isinstance(schedules, list) or len(schedules) > 50:
        raise ValueError("At most 50 schedules are supported.")
    for rule in schedules:
        if not isinstance(rule.get("name"), str) or not rule["name"].strip():
            raise ValueError("Schedules need a name.")
        if minutes(rule["start"]) == minutes(rule["end"]):
            raise ValueError("Schedule start and end must be different.")
        if not rule.get("days") or any(type(d) is not int or d not in range(7) for d in rule["days"]):
            raise ValueError("Choose at least one day.")
        if type(rule.get("enabled", True)) is not bool:
            raise ValueError("Invalid schedule state.")
    timer = config.get("timer")
    if timer is not None:
        if type(timer.get("block")) is not bool or not isinstance(timer.get("until"), (int, float)):
            raise ValueError("Invalid countdown timer.")
        import math
        if not math.isfinite(timer["until"]) or not 0 < timer["until"] < 32503680000:
            raise ValueError("Invalid timer end time.")
        if "started" in timer and (type(timer["started"]) not in (int, float)
                or not math.isfinite(timer["started"]) or not 0 < timer["started"] < timer["until"]):
            raise ValueError("Invalid timer start time.")
    return config


def load_config(path: Path) -> dict:
    if not path.exists():
        return defaults()
    try:
        return validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError(f"Settings could not be read. Original file preserved: {path}\n{exc}") from exc


def save_config(path: Path, config: dict) -> None:
    validate(copy.deepcopy(config))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def managed_range(data: bytes) -> tuple[int, int] | None:
    # Exact full-line markers avoid editing unrelated comments or mappings.
    lines = data.splitlines(keepends=True)
    start = end = None
    offset = 0
    for line in lines:
        content = line.rstrip(b"\r\n")
        if content == START:
            if start is not None or end is not None:
                raise ValueError("Multiple FocusTracker hosts markers; refusing to edit the file.")
            start = offset
        if content == END:
            if start is None or end is not None:
                raise ValueError("Invalid FocusTracker hosts markers; refusing to edit the file.")
            end = offset + len(line)
        offset += len(line)
    if (start is None) != (end is None):
        raise ValueError("Incomplete FocusTracker hosts block; restore it using the backup before retrying.")
    return None if start is None else (start, end)


def render_hosts(data: bytes, entries: list[str]) -> bytes:
    if b"\x00" in data:
        raise ValueError("UTF-16 hosts files are not supported; the hosts file was left untouched.")
    span = managed_range(data)
    newline = b"\r\n" if b"\r\n" in data or not data else b"\n"
    block = b""
    if entries:
        lines = [START]
        for host in expand_domains(entries):
            encoded = host.encode("ascii")
            lines.extend([b"0.0.0.0 " + encoded, b":: " + encoded])
        lines.append(END)
        block = newline.join(lines) + newline
    if span:
        return data[:span[0]] + block + data[span[1]:]
    if not block:
        return data
    return data + (newline if data and not data.endswith(b"\n") else b"") + block


class HostsFile:
    def __init__(self, path: Path, backup: Path):
        self.path, self.backup = path, backup

    def apply(self, entries: list[str]) -> bool:
        # Opening the existing file preserves its owner and ACLs. A byte-range lock
        # prevents concurrent writers while we read, back up, and change our block.
        with self.path.open("r+b") as stream:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 0x7fffffff)
            try:
                original = stream.read()
                updated = render_hosts(original, entries)
                if original == updated:
                    return False
                self.backup.parent.mkdir(parents=True, exist_ok=True)
                self.backup.write_bytes(original)
                try:
                    stream.seek(0)
                    stream.write(updated)
                    stream.truncate()
                    stream.flush()
                    os.fsync(stream.fileno())
                except OSError:
                    stream.seek(0)
                    stream.write(original)
                    stream.truncate()
                    stream.flush()
                    raise
                return True
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 0x7fffffff)
