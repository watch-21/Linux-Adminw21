#!/bin/sh
# Bootstrap only inside the disposable container created by linux_matrix.py.
set -eu
[ -f /.dockerenv ] || [ -f /run/.containerenv ] || { echo 'Disposable container marker required';exit 77; }
case ${1:-} in
 ubuntu22|ubuntu24|debian12|debian13|kali)
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends bash python3 python3-venv python3-pip passwd cron sudo util-linux iproute2 procps tar findutils coreutils grep sed fonts-dejavu-core libgl1 libegl1 libxkbcommon0 libfontconfig1 libglib2.0-0 libdbus-1-3 libx11-6 libxcb1 libfreetype6 ca-certificates
  ;;
 fedora)
  dnf -y install bash python3 python3-pip shadow-utils cronie sudo util-linux iproute procps-ng tar findutils coreutils grep sed dejavu-sans-fonts mesa-libGL mesa-libEGL libxkbcommon fontconfig glib2 dbus-libs libX11 libxcb freetype ca-certificates
  ;;
 arch)
  pacman -Syu --noconfirm --needed bash python python-pip shadow cronie sudo util-linux iproute2 procps-ng tar findutils coreutils grep sed ttf-dejavu mesa libxkbcommon fontconfig glib2 dbus libx11 libxcb freetype2 ca-certificates
  ;;
 opensuse)
  zypper --non-interactive refresh
  zypper --non-interactive install bash python3 python313 python313-pip shadow cron sudo util-linux iproute2 procps tar findutils coreutils grep sed dejavu-fonts Mesa-libGL1 libglvnd libxkbcommon0 fontconfig libglib-2_0-0 libgthread-2_0-0 libdbus-1-3 libX11-6 libxcb1 libfreetype6 ca-certificates
  ;;
 alpine)
  apk add --no-cache bash shadow shadow-login coreutils findutils grep sed util-linux iproute2 procps tar dcron sudo python3 py3-pip py3-psutil py3-pytest py3-pyside6 font-dejavu
  ;;
 *)echo 'Unknown container target';exit 2;;
esac
cp -R /source /work
cd /work
export QT_QPA_PLATFORM=offscreen
if [ "$1" = alpine ];then
 python3 -m pytest -q
else
 python3 -m venv /qa
 /qa/bin/python3 -m pip install -r requirements.txt -r requirements-dev.txt
 /qa/bin/python3 -m pytest -q
fi
for test in tests/test_*.sh;do bash "$test";done
ADMINW21_DISPOSABLE_CONTAINER=yes bash tests/integration_vm.sh --disposable-container
printf 'y\n' | bash install.sh --terminal-only
/usr/local/bin/adminw21 --version
printf 'y\n' | bash /usr/local/share/adminw21/uninstall.sh
echo 'PASS: container userspace checks; booted systemd/PolicyKit/native display not tested'
