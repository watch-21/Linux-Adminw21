# Linux Adminw21 v1

![Linux Adminw21 — Linux administration, desktop and terminal](docs/assets/banner.svg)

**Monitor your Linux system and manage everyday administration tasks from a native desktop window or the terminal.**

[Download ZIP](https://github.com/watch-21/Linux-Adminw21/archive/refs/heads/main.zip) · [Deutsch](docs/README.de.md) · [Requirements](docs/LINUX_DEPENDENCIES.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Feature scope](docs/FEATURE_STATUS.md)

Linux Adminw21 combines live resource monitoring with user, group, process, service and package management. The PySide6 desktop and Bash terminal interfaces share the same administration backend. The application supports **German and English**, with **light and dark** desktop themes.

## Features

| Area | What you can do |
|---|---|
| System dashboard | Inspect CPU, RAM, swap, disk and network usage with live charts and selectable history ranges |
| Users and groups | Manage accounts and membership; inspect visible login sessions and their groups |
| Processes | Search, filter, sort and inspect processes; send confirmed TERM/KILL signals to eligible targets |
| Services and packages | Inspect and manage supported systemd services and distribution package managers |
| Network | Inspect interfaces, addresses, routes, DNS and sockets; run bounded packet captures when available |
| Backups and Cron | Create and inspect backups, restore into protected empty destinations, and manage supported scheduled jobs |
| Files and security | Run supported file operations and inspect SSH, firewall, login and journal information |
| Reports | Collect and export timestamped TXT, JSON or HTML reports, including failed checks and source limitations |

Metric cards open the related view. Charts provide sample readouts and time ranges; page search and contextual action tiles make common tasks easier to reach.

See [feature scope and limitations](docs/FEATURE_STATUS.md) for each area.

## Install

Requirements: **Linux, Bash, Python 3.10+**, GNU coreutils/findutils and the native utilities used by each action. The desktop also needs Qt shared libraries, Python venv/pip, PolicyKit `pkexec` and a running desktop authorization agent.

1. [Download the source ZIP](https://github.com/watch-21/Linux-Adminw21/archive/refs/heads/main.zip), or clone the repository with `git clone https://github.com/watch-21/Linux-Adminw21.git`.
2. Extract it and open a terminal in the project folder.
3. Install the [system dependencies for your distribution](docs/LINUX_DEPENDENCIES.md).
4. Run:

```bash
sudo ./install.sh
adminw21 --gui
```

Run the GUI as your **normal desktop user**. Privileged actions request authentication through PolicyKit. Do not start the GUI with `sudo`.

The installer checks QtCore, QtGui, QtWidgets and psutil before reusing system packages. Missing, incomplete or incompatible Python packages select a private venv; downloading its dependencies requires package-index access. Native library failures produce diagnostics. The installer does not install or remove OS packages automatically.

### Terminal-only installation

For servers or systems without a desktop:

```bash
sudo ./install.sh --terminal-only
sudo adminw21 --terminal
```

The terminal uses `dialog` or `whiptail` when available, with a numbered-menu fallback.

## Use

- **Monitor resources:** open the dashboard, select a metric and choose a chart range. CPU and I/O rates need two samples before a value is available.
- **Inspect logged-in users:** open session details to see visible sessions, sources and groups. User accounts and active sessions are different; utmp can omit graphical logins.
- **Manage accounts:** open Users or Groups and choose an action. Password fields are masked and confirmed. Review administrative changes before submitting.
- **Inspect processes:** filter the process table, select a row and open details. Signal actions require confirmation and protect essential processes.
- **Export a report:** collect report data first, then choose TXT, JSON or HTML. Failed checks remain visible in the report.
- **Change appearance:** select German/English and light/dark in the interface. Preferences are saved per user.

Useful read-only CLI commands:

```bash
adminw21 --version
adminw21 --diagnose
adminw21 --health
adminw21 --users
```

`--users` lists account names; the desktop's sessions view provides login-session information.

## Update and uninstall

To update, download the new source and run `sudo ./install.sh` again. Installation stages and validates the application before switching, archives the previous files and rolls back after a failed switch.

- Application: `/usr/local/share/adminw21`
- Launcher: `/usr/local/bin/adminw21`
- Installation archives: `/var/backups/adminw21`

```bash
sudo /usr/local/share/adminw21/uninstall.sh
```

Uninstall checks owned registrations, removes the application's launchers/policy and archives the application tree. Settings, logs, data, backups and OS packages remain. Unknown legacy launchers require manual review.

## Compatibility and current limits

Support depends on the distribution's tools and permissions. Available package adapters include APT, DNF/YUM, Pacman, Zypper, APK, XBPS and Portage. Service mutations use systemd. Alpine requires native musl-compatible Qt packages; Python 3.10/3.11 uses PySide6 6.8.3.

The local regression record is **127 passed, 1 skipped**. It does not certify every Linux distribution, stock boot environment, real X11/Wayland session or desktop PolicyKit prompt. Package writes, service mutations, scheduled daemon execution, firewall changes and capture need further native-environment verification.

Backup restore rejects linked/special archive entries and requires an empty root-controlled destination. Cron editing supports numeric schedules and fixed tasks. These and other boundaries are documented in [Linux compatibility](docs/LINUX_COMPATIBILITY.md), [feature scope](docs/FEATURE_STATUS.md) and the [test report](docs/TEST_REPORT.md).

## Documentation and development

- [Linux dependencies](docs/LINUX_DEPENDENCIES.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture and data locations](docs/ARCHITECTURE.md)
- [Validation and development checks](docs/TEST_REPORT.md)
- [Disposable QEMU testing](docs/QEMU_TESTING.md)
- [Changes](docs/CHANGELOG.md)

Install development dependencies in a dedicated environment and run `bash tests/run.sh`. Real account/Cron/install integration must run only in a disposable VM, following the test documentation.

For bug reports, include the distribution, Python version, interface mode, reproduction steps and exact error. Remove passwords, private keys and personal system details from logs before sharing them.
