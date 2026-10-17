#!/bin/sh
# This script changes accounts/packages only inside the disposable QEMU test VM.
set -eu
[ "${ADMINW21_DISPOSABLE_VM:-}" = yes ] && grep -qw 'adminw21.disposable=1' /proc/cmdline || exit 77
# A custom VM init must create the standard proc-backed descriptors and shared memory.
/qa/busybox ln -snf /proc/self/fd /dev/fd
/qa/busybox ln -snf /proc/self/fd/0 /dev/stdin
/qa/busybox ln -snf /proc/self/fd/1 /dev/stdout
/qa/busybox ln -snf /proc/self/fd/2 /dev/stderr
/qa/busybox modprobe virtio_rng
/qa/busybox mkdir -p /dev/shm
if ! grep -q ' /dev/shm ' /proc/mounts;then /qa/busybox mount -t tmpfs -o mode=1777 tmpfs /dev/shm;fi
if [ "${ADMINW21_PROBE:-no}" = yes ];then exec /bin/bash /qa-probe.sh;fi
# Trust the optional host test proxy CA using native trust stores; keep TLS verification enabled.
if [ -f /qa-cert.pem ];then
 for directory in /usr/local/share/ca-certificates /etc/pki/ca-trust/source/anchors /etc/pki/trust/anchors /etc/ca-certificates/trust-source/anchors;do
  mkdir -p "$directory"
  cp /qa-cert.pem "$directory/adminw21-qa.crt"
 done
 for bundle in /etc/ssl/cert.pem /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt /etc/ssl/ca-bundle.pem /var/lib/ca-certificates/ca-bundle.pem;do
  [ ! -f "$bundle" ] || cat /qa-cert.pem >>"$bundle"
 done
 if command -v update-ca-trust >/dev/null;then update-ca-trust extract;elif command -v update-ca-certificates >/dev/null;then update-ca-certificates;fi
fi
export XDG_CACHE_HOME=/root/.cache
mkdir -p "$XDG_CACHE_HOME"
key=$1
echo ADMINW21_PHASE=bootstrap
export DEBIAN_FRONTEND=noninteractive
if [ ! -f /qa-core-deps ] || [ "$(cat /qa-core-deps)" != "$key" ] || ! command -v python3 >/dev/null;then
case $key in
 ubuntu22|ubuntu24|debian12|debian13|kali)
  for source in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources;do
   [ ! -f "$source" ] || sed -i 's@http://@https://@g' "$source"
  done
  if [ -f /qa-cert.pem ];then printf 'Acquire::https::CaInfo "/qa-cert.pem";\n' >/etc/apt/apt.conf.d/99-adminw21-qa-cert;fi
  if ! dpkg --configure -a;then apt-get -y -o Acquire::Retries=2 -f install;fi
  apt-get -o Acquire::http::Pipeline-Depth=0 -o Acquire::https::Pipeline-Depth=0 -o Acquire::http::Timeout=25 -o Acquire::https::Timeout=25 -o Acquire::Retries=2 -o APT::Update::Error-Mode=any update
  apt-get -y -o Acquire::http::Timeout=25 -o Acquire::https::Timeout=25 -o Acquire::Retries=2 install --no-install-recommends bash python3 python3-venv python3-pip passwd cron sudo util-linux iproute2 procps tar findutils coreutils grep sed ca-certificates
  ;;
 fedora)dnf --setopt=retries=0 --setopt=timeout=25 -y install bash python3 python3-pip shadow-utils cronie sudo util-linux iproute procps-ng tar findutils coreutils grep sed ca-certificates;;
 arch)pacman -Syu --noconfirm --needed bash python python-pip shadow cronie sudo util-linux iproute2 procps-ng tar findutils coreutils grep sed ca-certificates;;
 opensuse)
  zypper --non-interactive refresh
  zypper --non-interactive install bash python3 python313 python313-pip shadow cron sudo util-linux iproute2 procps tar findutils coreutils grep sed ca-certificates
  ;;
 alpine)apk add --no-cache bash shadow shadow-login coreutils findutils grep sed util-linux iproute2 procps tar dcron sudo python3 py3-pip py3-psutil py3-pytest;;
 *)exit 2;;
esac
printf '%s\n' "$key" >/qa-core-deps
fi
echo ADMINW21_PHASE=core
cd /source
for test in tests/test_*.sh;do timeout 120 bash "$test";done
ADMINW21_DISPOSABLE_VM=yes timeout 120 bash tests/integration_vm.sh --disposable-vm
bash install.sh --terminal-only --yes
/usr/local/bin/adminw21 --version
bash /usr/local/share/adminw21/uninstall.sh --yes
echo 'ADMINW21_CORE_RESULT=0'
if [ "${ADMINW21_CORE_ONLY:-no}" = yes ];then exit 0;fi
echo ADMINW21_PHASE=gui_bootstrap
probe_python=python3
[ ! -x /qa/bin/python3 ] || probe_python=/qa/bin/python3
if ! QT_QPA_PLATFORM=offscreen "$probe_python" -I -c 'from PySide6.QtWidgets import QApplication;import psutil;app=QApplication([])' 2>/dev/null;then
case $key in
 ubuntu22|ubuntu24|debian12|debian13|kali)apt-get -y -o Acquire::http::Timeout=25 -o Acquire::https::Timeout=25 -o Acquire::Retries=2 install --no-install-recommends fonts-dejavu-core libgl1 libegl1 libxkbcommon0 libfontconfig1 libglib2.0-0 libdbus-1-3 libx11-6 libxcb1 libfreetype6;;
 fedora)dnf --setopt=retries=0 --setopt=timeout=25 -y install dejavu-sans-fonts mesa-libGL mesa-libEGL libxkbcommon fontconfig glib2 dbus-libs libX11 libxcb freetype;;
 arch)pacman -S --noconfirm --needed ttf-dejavu mesa libxkbcommon fontconfig glib2 dbus libx11 libxcb freetype2;;
 opensuse)zypper --non-interactive install dejavu-fonts Mesa-libGL1 libglvnd libxkbcommon0 fontconfig libglib-2_0-0 libgthread-2_0-0 libdbus-1-3 libX11-6 libxcb1 libfreetype6;;
 alpine)apk add --no-cache py3-pyside6 font-dejavu;;
esac
fi
export QT_QPA_PLATFORM=offscreen PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
echo ADMINW21_PHASE=pytest
if [ "$key" = alpine ];then
 python3 -I gui/runtime_check.py
 timeout 240 python3 -m pytest -x -vv --tb=short -o faulthandler_timeout=45
else
 [ -x /qa/bin/python3 ] || python3 -m venv /qa
 /qa/bin/python3 -m pip install --no-index --find-links /wheels -r requirements.txt -r requirements-dev.txt
 /qa/bin/python3 -I gui/runtime_check.py
 timeout 240 /qa/bin/python3 -m pytest -x -vv --tb=short -o faulthandler_timeout=45
fi
echo 'ADMINW21_PYTEST_RESULT=0'
