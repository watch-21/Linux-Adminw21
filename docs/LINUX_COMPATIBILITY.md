# Linux compatibility — v1

Runtime support is capability-based: Linux, Bash, Python 3.10+, GNU tools and the native utilities used by each action. Unsupported actions return an unavailable/error status. Desktop operation requires working Qt libraries, `pkexec` and a desktop authorization agent. See [LINUX_DEPENDENCIES.md](LINUX_DEPENDENCIES.md).

| Environment | Available integration | Validation boundary |
|---|---|---|
| Debian, Ubuntu, Kali | APT and systemd adapters; Qt wheel/private venv setup | Native package writes, stock boot and desktop authorization require disposable VM checks |
| Fedora | DNF/YUM and systemd adapters | Native package writes and desktop behavior require disposable VM checks |
| Arch | Pacman and systemd adapters | Rolling packages and native desktop behavior require fresh checks |
| openSUSE | Zypper and systemd adapters | Native package writes and desktop behavior require disposable VM checks |
| Alpine | APK, native musl Qt packages and terminal mode | OpenRC service mutation is unavailable; glibc Qt wheels are unsuitable |
| Void/Gentoo | XBPS/Portage package adapters | No complete distribution validation; non-systemd service mutation is unavailable |
| Immutable systems | Capability detection and supported read actions | NixOS/OSTree package mutation is unavailable |

Python 3.10/3.11 is constrained to PySide6 6.8.3 to avoid an older-CPython incompatibility in Qt 6.12. Runtime preflight rejects unsupported combinations and distinguishes missing Python modules from native library failures.

Current local checks are documented in [TEST_REPORT.md](TEST_REPORT.md). This release does not certify all Linux distributions, hardware architectures, stock kernels, X11/Wayland sessions or desktop PolicyKit prompts.

`tests/linux_matrix.py` provides disposable Docker/Podman userspaces. `tests/qemu_matrix.py` provides disposable x86_64 QEMU guests with a common kernel; see [QEMU_TESTING.md](QEMU_TESTING.md). Container results share the host kernel; QEMU userspace results do not validate each distribution's stock boot stack. The manual CI workflow runs only when explicitly dispatched.
