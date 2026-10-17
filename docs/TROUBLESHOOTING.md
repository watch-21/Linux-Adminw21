# Troubleshooting — Linux Adminw21 v1

## Missing QtWidgets or other Python GUI modules

Re-run `sudo ./install.sh` from the current source folder. The installer imports QtCore, QtGui, QtWidgets and psutil before accepting system packages. Missing, incomplete or incompatible packages select a private venv. Venv support and package-index access must be available.

A namespace named PySide6 alone is insufficient. Do not copy individual Qt modules into the application folder. Use the installer to prepare a consistent runtime.

## Qt native library errors

Install the [native dependencies](LINUX_DEPENDENCIES.md) for the distribution and retry installation. Python wheels do not supply every OS library. The installer prints the load error and keeps the current application until staging completes.

Alpine requires its native musl-compatible Python/Qt packages. Python 3.10/3.11 uses the compatible PySide6 6.8 branch selected by the runtime requirements.

## No desktop display or GUI started as root

Run `adminw21 --gui` from the normal user's active desktop session. It requires a visible display and rejects root execution. For headless use, install with `--terminal-only` and run `sudo adminw21 --terminal`.

## Administrative action cannot authenticate

Check that `pkexec` and a desktop PolicyKit agent are available. Privileged GUI actions require installation at the fixed path `/usr/local/share/adminw21`; a copied development folder cannot be elevated. Root-owned code and registration guards are intentional.

## An old launcher opens another installation

Inspect the command resolution:

```bash
type -a adminw21 linux-admin
/usr/local/bin/adminw21 --version
```

The installer preserves unknown and user-local legacy launchers for manual review. Check their targets before deciding which obsolete files to remove.

## Blank rates, missing sessions or unavailable actions

CPU and I/O rates need two real samples. Session visibility depends on logind/utmp and permissions; an empty source is not replaced with an invented login. Native tools, systemd and access permissions differ between environments. Inspect the displayed source/error and the [feature scope](FEATURE_STATUS.md).

## Collect information for a bug report

Record the distribution, Python version, interface mode and exact steps. Run `adminw21 --diagnose` and inspect the output before sharing: it contains account, home and display information. Remove private paths, usernames, remote addresses, passwords and keys from any shared diagnostics.
