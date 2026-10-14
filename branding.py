"""Resolve source and PyInstaller-bundled brand assets without absolute paths."""
from pathlib import Path
import sys

VERSION = "1.3.4"


def asset(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / name
