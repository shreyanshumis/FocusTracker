# FocusTracker

<img src="assets/logo.png" width="180" alt="FocusTracker eye logo">

A local website blocker for **Windows 10/11 x64 laptops and PCs**. Choose
websites, run a focus countdown, or set weekly schedules. YouTube gets an
?Are you sure it's about studies?? prompt instead of a hard block.

The desktop interface uses navy, blue, and cyan with hover transitions, page
animations, a live countdown progress bar, and a **Reduce motion** setting.
No account, telemetry, cloud service, or browsing-history log.

## Install and use

1. Run `FocusTracker-Setup-1.3.2.exe` and approve Windows administrator access.
   Python is bundled; it does not need to be installed separately.
2. Open FocusTracker from Start. Add your website domains or paste URLs.
   New installations start with an empty list, with no preset websites.
   `reddit.com`, `www.reddit.com`, and `https://www.reddit.com/` all become
   one `reddit.com` entry. Paths, query strings, and fragments are ignored.
   Use **Block now** to keep your list blocked until you choose **Unblock now**.
   Timers and schedules remain optional. **Remove selected** or **Remove all**
   lets you clear your choices. Upgrades preserve saved lists; use **Remove all**
   to clear websites left over from an older version.
3. Install the included browser companion in **each Chrome/Edge profile**:
   open the Start-menu **Browser companion folder** shortcut; open
   `chrome://extensions` or `edge://extensions`, enable Developer mode, choose
   **Load unpacked**, and select that folder. Reload the extension after upgrades.
4. Choose **Block now**, start a focus countdown, or choose **Use schedules**.
   Keep FocusTracker running. Closing its window hides it in the system tray.

The app footer reports whether a companion has recently connected; this does
not prove every browser/profile is configured. Opening the companion popup
refreshes its policy immediately. Automatic checks normally occur within 30
seconds. Listed non-YouTube websites show a blocked screen, including tabs
already open. The extension handles subdomains too. YouTube's prompt does not
inspect video content; accepting it allows the requested navigation.

Without the companion, Windows hosts rules cover the exact listed domains
and their www aliases in browsers using Windows name resolution. Add other
subdomains explicitly for hosts blocking. Cached connections, custom DNS,
VPNs, or proxies may bypass hosts rules. Restart browsers if needed.
The companion supports Chrome/Edge, not Firefox. This is a voluntary focus
tool, not a tamper-proof parental-control system. It blocks gaming websites,
not installed games.

## Timers, schedules, and recovery

- Manual block/unblock cancels the current timer and remains until you change mode.
- Countdown expiry restores the selected manual or schedule mode.
- Weekly schedules use local PC time. Overnight schedules start on the selected day.
- The app must run for timed changes. After sleep it catches up with current time.
- Startup is manual. Use **Unblock & quit** to remove its hosts rules and exit.
- If it crashes, reopen it or use **Recover blocked websites** in Start.

## Uninstall

Choose **Unblock & quit**, then remove FocusTracker from Windows **Installed
apps / Apps & features**, or use its Start-menu uninstaller. The uninstaller
cleans up FocusTracker's hosts rules before deleting its files; unrelated
hosts entries are preserved. Cleanup failure stops uninstall so recovery is
still available. Remove the browser companion separately in each browser.
Personal settings/backups remain in `%LOCALAPPDATA%\FocusHarbor`; delete that
folder after uninstall if you want to erase them too.

The portable ZIP runs without installation; extract it to a permanent folder
before loading its extension. To remove it, unblock and quit, remove the
extension, then delete the extracted folder. Both versions need administrator
rights for hosts changes. The installer/executable are currently unsigned.

## Build from source

Use Windows x64, Python 3.14 with Tcl/Tk, and [Inno Setup 6](https://jrsoftware.org/isinfo.php).
Run these commands inside this source folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/extension.test.cjs
.\.venv\Scripts\python.exe tests/ui_smoke.py
.\.venv\Scripts\python.exe build_app.py
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installer.iss
.\.venv\Scripts\python.exe package_release.py
```

Output in `release/`: installer EXE, portable ZIP, source ZIP, and SHA-256
checksums. Build in a clean virtual environment. No system hosts changes are
needed to build or test. Run `main.py` without `--demo` for real blocking.

Optional real-browser integration tests use an isolated Chromium profile:

```powershell
npm install --no-save playwright-core
npx playwright-core install chromium
node tests/browser.e2e.cjs
```

The test can also use `FOCUS_PLAYWRIGHT` and `FOCUS_CHROMIUM` paths to existing
test installations. It never uses personal profiles. See the official
[Playwright extension testing guide](https://playwright.dev/docs/chrome-extensions).

## Put the project on GitHub

This folder is the repository root. Alternatively, extract the **Source.zip**
and use its `FocusTracker` directory as the repository root. It includes code,
logo, tests, documentation, MIT code license, and
`.github/workflows/windows.yml`. It excludes local settings, binaries, browser
profiles, and unrelated projects. Create a new GitHub repository and upload
these source files, including `.github` and `.gitignore`.

For a local Git checkout, review the staged files, make your first commit, and
connect an empty repository created in your GitHub account:

```powershell
git status
git diff --cached --stat
git commit -m "Initial FocusTracker release"
git remote add origin https://github.com/YOUR-USERNAME/focustracker.git
git push -u origin main
```

Local `_archive/` and `.tools/` directories are ignored. They are not needed
by people cloning the repository. Keep the contents of `release/` as GitHub
Release attachments rather than committing the compiled downloads to Git.

The included [GitHub Actions workflow](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
tests and builds Windows packages as Actions artifacts. It requires Inno Setup
6 on the runner, and has not been executed on GitHub yet. Create a GitHub
Release manually and attach the installer, portable ZIP, and checksums from
`release/`. This project does not publish automatically.

## Architecture and privacy

FocusTracker was previously named Focus Harbor. The installer keeps the same
application ID so an existing installation can be upgraded. Settings remain
in `%LOCALAPPDATA%\FocusHarbor`; legacy hosts markers, process mutexes, and the
local companion protocol retain their identifiers for compatibility. Reload
the browser companion after upgrading to display its new name.

`core.py` handles validation, schedules, and scoped hosts edits. `main.py` and
`theme.py` provide the native UI, tray, and worker threads. `bridge.py` exposes
read-only focus policy on `127.0.0.1:47653`; local processes may read this list.
The browser companion applies request rules and checks open tabs locally.
It needs website access to block navigation and replace already-open tabs.
No browsing history is written or sent to a remote service.

The logo is a close recreation of the supplied reference because the original
file was unavailable. See [asset provenance](assets/README.md) and
[third-party notices](THIRD-PARTY-NOTICES.md). Code is MIT licensed; brand
artwork and third-party licenses are separate.
