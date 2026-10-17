#!/bin/bash
# Installs/registers/removes only inside an explicitly disposable QEMU guest.
set -euo pipefail
[[ $EUID == 0 && ${ADMINW21_DISPOSABLE_VM:-} == yes ]] || exit 77
grep -qw 'adminw21.disposable=1' /proc/cmdline || exit 77
command -v pkexec >/dev/null || { echo 'Desktop test requires native pkexec';exit 69; }
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
export QT_QPA_PLATFORM=offscreen
if [[ -d /wheels ]];then export PIP_NO_INDEX=1 PIP_FIND_LINKS=/wheels;fi
bash "$ROOT/install.sh" --yes
[[ $(/usr/local/bin/adminw21 --version) == v1 ]]
[[ -f /usr/share/applications/adminw21.desktop ]]
python3 - <<'PY'
import xml.etree.ElementTree as ET
root = ET.parse('/usr/share/polkit-1/actions/org.adminw21.backend.policy').getroot()
assert root.find("action/annotate[@key='org.freedesktop.policykit.exec.path']").text == '/usr/local/share/adminw21/backend/backend.sh'
PY
python=python3
[[ ! -x /usr/local/share/adminw21/venv/bin/python3 ]] || python=/usr/local/share/adminw21/venv/bin/python3
"$python" -I /usr/local/share/adminw21/gui/runtime_check.py
"$python" -I -c 'from PySide6.QtWidgets import QApplication;import psutil;app=QApplication([]);print("PASS: installed Qt runtime")'
bash /usr/local/share/adminw21/uninstall.sh --yes
[[ ! -e /usr/local/bin/adminw21 && ! -e /usr/share/applications/adminw21.desktop && ! -e /usr/share/polkit-1/actions/org.adminw21.backend.policy ]]
echo 'ADMINW21_DESKTOP_INSTALL_RESULT=0'
echo 'PolicyKit agent authentication and a live desktop session were not tested'
