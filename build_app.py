"""Build a portable executable and its recovery/preview launchers."""
from pathlib import Path
import shutil
import subprocess
import sys
from importlib.metadata import distribution
from PIL import Image
from branding import VERSION

root = Path(__file__).resolve().parent
dist = root / "dist-study"
assets = root / "build"
assets.mkdir(exist_ok=True)
icon = Image.open(root / "assets" / "logo.png").convert("RGBA")
icon = icon.resize((256, 256), Image.Resampling.LANCZOS)
icon.save(assets / "focus.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
for size in (16, 32, 48, 128):
    icon.resize((size, size), Image.Resampling.LANCZOS).save(root / "youtube-extension" / f"icon{size}.png")
shutil.copy2(root / "assets" / "logo.png", root / "youtube-extension" / "logo.png")
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                "--onefile", "--windowed", "--name", "FocusTracker", "--distpath", str(dist),
                "--icon", str(assets / "focus.ico"), "--hidden-import", "pystray._win32",
                "--add-data", str(root / "assets") + ";assets",
                "--exclude-module", "numpy",
                str(root / "main.py")], cwd=root, check=True)
for name in ("Recover websites.cmd", "Preview.cmd", "README.md", "LICENSE", "THIRD-PARTY-NOTICES.md", "INSTALL-NOTES.txt"):
    shutil.copy2(root / name, dist / name)
shutil.copytree(root / "youtube-extension", dist / "youtube-extension", dirs_exist_ok=True)
licenses = dist / "licenses"
licenses.mkdir(exist_ok=True)
for package in ("Pillow", "pystray", "six", "PyInstaller"):
    metadata = distribution(package)
    for file in metadata.files:
        if file.name.lower().startswith(("license", "copying")):
            shutil.copy2(metadata.locate_file(file), licenses / (package + "-" + file.name))
shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python-LICENSE.txt")
for index, file in enumerate((Path(sys.base_prefix) / "tcl").rglob("license.terms")):
    shutil.copy2(file, licenses / f"TclTk-{index}-license.terms")
print("Portable app ready:", dist / "FocusTracker.exe")
