# Validation — Linux Adminw21 v1

Validation date: 2026-10-17. Local environment: Linux x86_64, Python 3.12, PySide6 6.12.0, Qt offscreen platform.

| Check | Result |
|---|---|
| Python regression suite | 127 passed, 1 skipped |
| Bash syntax and regression suites | Passed |
| Python compilation | Passed |
| Ruff | Passed |
| ShellCheck | Passed |
| Release contents | Source, tests and technical documentation; checksums cover all shipped files except the checksum manifest itself |

Run `bash tests/run.sh` with the dependencies in `requirements.txt` and `requirements-dev.txt`. The process-signalling test skips when its disposable child's `/proc` identity is unavailable. Some installation/backup tests require root-owned temporary fixtures and skip when run without root.

The suite covers action routing/input validation, password framing, backup safeguards, runtime preflight, installer rollback, session parsing/groups, report exports and native Qt interaction/layout/lifecycle regressions. Optional real account/Cron/install integration is separate and changes disposable fixtures; run it only in a throwaway VM.

This local run does not validate stock distribution boot, real X11/Wayland sessions, desktop PolicyKit authentication, systemd mutations, native package writes, scheduled daemon execution, firewall changes, capture or ARM hardware. No new cross-distribution run is included in this validation. See [LINUX_COMPATIBILITY.md](LINUX_COMPATIBILITY.md) and [QEMU_TESTING.md](QEMU_TESTING.md) for scope and reproduction.
