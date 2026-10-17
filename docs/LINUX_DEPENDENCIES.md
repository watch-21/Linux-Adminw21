# Linux runtime dependencies — v1

Python 3.10+, Bash, GNU coreutils/findutils and the native account/package tools are required. Desktop installation also needs PolicyKit `pkexec`, a running desktop authorization agent, and Qt's native shared libraries. Python wheels alone do not provide all of those libraries.

The installer reuses a system PySide6/psutil installation only after importing QtCore, QtGui and QtWidgets and validating the supported version. A partial/missing Python package selects a private venv. Otherwise it creates a private venv. If Qt cannot load its shared libraries, installation stops before replacing the current application and prints the missing library and this guide's path. No OS packages are installed automatically.

## Ubuntu / Debian

```bash
sudo apt update
sudo apt install bash python3 python3-venv python3-pip pkexec fonts-dejavu-core libgl1 libegl1 libxkbcommon0 libfontconfig1 libglib2.0-0 libdbus-1-3 libx11-6 libxcb1 libfreetype6
```

On releases with the time64 transition, APT resolves the corresponding `t64` library package names.

## Fedora

```bash
sudo dnf install bash python3 python3-pip polkit dejavu-sans-fonts mesa-libGL mesa-libEGL libxkbcommon fontconfig glib2 dbus-libs libX11 libxcb freetype
```

## Arch

```bash
sudo pacman -Syu --needed bash python python-pip polkit ttf-dejavu mesa libxkbcommon fontconfig glib2 dbus libx11 libxcb freetype2
```

## openSUSE Leap 16

```bash
sudo zypper install bash python3 python313 python313-pip polkit dejavu-fonts Mesa-libGL1 libglvnd libxkbcommon0 fontconfig libglib-2_0-0 libgthread-2_0-0 libdbus-1-3 libX11-6 libxcb1 libfreetype6
```

## Alpine

Use the distribution's musl-compatible Qt package:

```bash
sudo apk add bash shadow shadow-login coreutils findutils util-linux python3 py3-psutil py3-pyside6 font-dejavu polkit
```

Then install the application:

```bash
sudo ./install.sh
adminw21 --gui
```

Run the GUI as the desktop user. Administrative actions request authorization through `pkexec`. Terminal-only installation is `sudo ./install.sh --terminal-only` and does not require Qt or a desktop agent. See `LINUX_COMPATIBILITY.md` for actual test results and remaining desktop/boot limitations.

Python 3.10/3.11 uses the validated PySide6 6.8.3 wheel. A reproduced None-reference regression in the 6.12.0 bindings aborts older CPython; the installer and launcher reject that combination and select the compatible private environment. Newer Python and native Alpine Qt retain the supported modern range.
