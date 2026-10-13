# Contributing

Use a Windows 10/11 x64 PC and Python 3.14. Follow README.md for setup and tests.
Preview mode and automated tests use temporary hosts files. Never test by
modifying a contributor's real hosts file or browser profile.

Keep settings backward compatible and preserve unrelated hosts entries. Include
tests for changes to schedules, blocking, timer expiry, or recovery. Explain
behavior changes and validation in pull requests. Do not commit personal
settings, browser profiles, compiled binaries, or machine-specific paths.

Version changes must update `branding.py`, `installer.iss`, and
`youtube-extension/manifest.json`. The bridge protocol version is independent.

The Windows workflow tests and packages the app as a downloadable Actions
artifact. Publishing a GitHub Release is a separate manual step.
