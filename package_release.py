"""Package only explicitly selected project files, never parent-workspace data."""
from pathlib import Path
import hashlib
import zipfile
from branding import VERSION

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "release"
FILES = ["main.py", "core.py", "bridge.py", "theme.py", "branding.py",
         "installer_cleanup.py", "app_signals.py", "build_app.py", "package_release.py", "installer.iss",
         "requirements.txt", "README.md", "INSTALL-NOTES.txt", "LICENSE",
         "THIRD-PARTY-NOTICES.md", "CONTRIBUTING.md", ".gitignore", ".gitattributes",
         "Preview.cmd", "Recover websites.cmd"]
FOLDERS = ["tests", "youtube-extension", ".github"]

def archive(target, files, base, prefix=""):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(files):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                bundle.write(path, prefix + path.relative_to(base).as_posix())

if __name__ == "__main__":
    OUTPUT.mkdir(exist_ok=True)
    source = [ROOT / name for name in FILES]
    for folder in FOLDERS:
        source.extend((ROOT / folder).rglob("*"))
    for path in [ROOT / name for name in FILES]:
        if not path.is_file():
            raise SystemExit(f"Missing source file: {path.name}")
    archive(OUTPUT / f"Blacklist-{VERSION}-Source.zip", source, ROOT, "Blacklist/")
    portable = ROOT / "dist-study"
    if not (portable / "Blacklist.exe").is_file():
        raise SystemExit("Run build_app.py first.")
    archive(OUTPUT / f"Blacklist-{VERSION}-Portable-Windows.zip", portable.rglob("*"), portable)
    import shutil
    setup = ROOT / "installer-output" / f"Blacklist-Setup-{VERSION}.exe"
    if not setup.is_file():
        raise SystemExit("Compile installer.iss first.")
    shutil.copy2(setup, OUTPUT / setup.name)
    artifacts = [OUTPUT / setup.name, OUTPUT / f"Blacklist-{VERSION}-Source.zip",
                 OUTPUT / f"Blacklist-{VERSION}-Portable-Windows.zip"]
    (OUTPUT / "SHA256SUMS.txt").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts), encoding="utf-8")
    print("Release files:", OUTPUT)
