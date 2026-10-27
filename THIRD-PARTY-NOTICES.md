# Third-party notices

Blacklist uses Python (PSF license), Tcl/Tk (Tcl/Tk licenses), Pillow (HPND),
pystray (LGPL-3.0), and six (MIT). Its executable is built with PyInstaller
(GPL with its bootloader exception). See the bundled `licenses` directory for
the dependency notices from the build environment. Source builds can replace
the dependencies through `requirements.txt` and rebuild the executable.

The installer is compiled with Inno Setup. Its compiler is a development
tool and is not bundled in the source project. Obtain it from
https://jrsoftware.org/isinfo.php and follow its license terms.
