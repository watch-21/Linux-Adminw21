#!/bin/bash
set -Eeuo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
mode=desktop;yes=no
while (($#));do
 case $1 in
  --help|-h)echo 'sudo ./install.sh [--terminal-only] [--yes] [--destdir /staging/root]';exit 0;;
  --terminal-only)mode=terminal;;--yes)yes=yes;;
  --destdir)shift;[[ $# -gt 0 ]] || exit 2;DESTDIR=$1;;
  *)echo "Unknown option: $1" >&2;exit 2;;
 esac
 shift
done
((EUID==0)) || { echo 'Run sudo ./install.sh' >&2;exit 77; }
[[ ${PREFIX:-/usr/local} == /usr/local ]] || { echo 'Runtime prefix is fixed at /usr/local' >&2;exit 2; }
source "$ROOT/lib/install_paths.sh"
aw_install_base
aw_install_preflight
printf 'Linux Adminw21 v1 · %s\nApplication: %s\n' "$mode" "$AW_DEST"
for file in "${AW_FILES[@]}" "$AW_BASE/root/.local/bin/linux-admin" "$AW_BASE/root/.local/bin/adminw21";do
 [[ ! -e $file ]] || ls -ld -- "$file"
done
echo 'Settings/logs remain untouched. Existing application and registrations will be archived.'
[[ $mode != terminal ]] || echo 'Terminal-only mode removes the owned GUI launcher and policy.'
if [[ $yes != yes ]];then read -r -p 'Install? [y/N]: ' answer;[[ $answer == y || $answer == Y ]] || exit 0;fi
for binary in bash python3 awk sed grep stat find realpath getent tar install flock;do
 command -v "$binary" >/dev/null || { echo "Required utility missing: $binary" >&2;exit 69; }
done
python3 -I -c 'import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo 'Python 3.10+ required';exit 69; }
if [[ $mode == desktop ]];then command -v pkexec >/dev/null || { echo 'Install PolicyKit/pkexec before desktop installation';exit 69; };fi
install -d -m 755 -- "$AW_BASE/usr/local/share" "$AW_BASE/usr/local/bin" "$AW_BASE/usr/share/applications" "$AW_BASE/usr/share/polkit-1/actions"
stage=$(mktemp -d "$AW_BASE/usr/local/share/.adminw21-stage.XXXXXXXX")
switched=no;old_moved=no;new_installed=no;committed=no
on_exit() {
 local status=$?
 trap - EXIT INT TERM
 if [[ $committed != yes && $switched == yes ]];then
  set +e
  echo 'Installation failed; restoring previous installation.' >&2
  if [[ $new_installed == yes && -d $AW_DEST && -f $AW_DEST/.adminw21-owned ]];then mv -- "$AW_DEST" "$AW_BACKUP/failed-application";fi
  if [[ $old_moved == yes ]];then mv -- "$AW_BACKUP/application" "$AW_DEST";fi
  aw_install_restore_registration || echo "Registration recovery requires review: $AW_BACKUP" >&2
 fi
 if ((status!=0));then echo "Staging/diagnostics: $stage" >&2;fi
 exit "$status"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for directory in lib lang modules config gui backend packaging docs tests;do
 [[ -d $ROOT/$directory ]] || exit 2
 cp -R -- "$ROOT/$directory" "$stage/$directory"
done
for file in admin.sh install.sh uninstall.sh requirements.txt requirements-dev.txt README.md pyproject.toml .shellcheckrc;do
 cp -- "$ROOT/$file" "$stage/$file"
done
[[ -z $(find "$stage" -type l -print -quit) ]] || { echo 'Source symlinks refused';exit 2; }
printf 'Linux Adminw21 v1\n' >"$stage/.adminw21-owned"
printf '%s\n' "$mode" >"$stage/.adminw21-mode"
if [[ $mode == desktop ]];then
 runtime_status=0
 python3 -I "$stage/gui/runtime_check.py" >"$stage/gui-preflight.log" 2>&1 || runtime_status=$?
 case $runtime_status in
  0)python=python3;;
  69)
  echo 'System GUI Python packages missing, incomplete or incompatible; preparing a private environment.'
  python3 -m venv "$stage/venv" || { echo 'Install Python venv support';exit 69; }
  "$stage/venv/bin/python3" -I -m pip install -r "$stage/requirements.txt"
  python="$stage/venv/bin/python3"
  ;;
  *)
  cat "$stage/gui-preflight.log" >&2
  echo 'Qt could not load native libraries. See docs/LINUX_DEPENDENCIES.md.' >&2
  exit 69;;
 esac
 if ! QT_QPA_PLATFORM=offscreen "$python" -I "$stage/gui/runtime_check.py" --smoke >"$stage/gui-preflight.log" 2>&1;then
  cat "$stage/gui-preflight.log" >&2
  echo 'GUI startup failed; see the diagnostic above and docs/LINUX_DEPENDENCIES.md.' >&2
  exit 69
 fi
fi
find "$stage" -type d -exec chmod 755 {} +
find "$stage" -type f -exec chmod go-w {} +
find "$stage" -name '*.sh' -exec chmod 755 {} +
chown -R root:root "$stage"
for script in "$stage/admin.sh" "$stage/backend/backend.sh";do bash -n "$script";done
[[ $("$stage/admin.sh" --version) == v1 ]]
aw_install_snapshot
switched=yes
if [[ -d $AW_DEST ]];then mv -- "$AW_DEST" "$AW_BACKUP/application";old_moved=yes;fi
mv -- "$stage" "$AW_DEST"
new_installed=yes
aw_install_atomic "$AW_DEST/packaging/adminw21.launcher" "$AW_LAUNCHER" 755
aw_install_atomic "$AW_DEST/packaging/adminw21-terminal.desktop" "${AW_FILES[2]}" 644
if [[ $mode == desktop ]];then
 aw_install_atomic "$AW_DEST/packaging/adminw21.desktop" "${AW_FILES[1]}" 644
 aw_install_atomic "$AW_DEST/packaging/org.adminw21.backend.policy" "${AW_FILES[3]}" 644
else
 for file in "${AW_FILES[1]}" "${AW_FILES[3]}";do [[ ! -f $file ]] || rm -- "$file";done
fi
[[ $("$AW_DEST/admin.sh" --version) == v1 ]]
"$AW_DEST/backend/backend.sh" capabilities
if [[ $mode == desktop && -x $AW_DEST/venv/bin/python3 ]];then QT_QPA_PLATFORM=offscreen "$AW_DEST/venv/bin/python3" -I "$AW_DEST/gui/runtime_check.py" --smoke;fi
committed=yes
if [[ -n $AW_BASE ]];then echo "Staged package: $AW_BASE (not registered on this host)"
else echo 'Installed: adminw21 --gui  |  sudo adminw21 --terminal';fi
echo "Previous files/recovery: $AW_BACKUP"
echo 'Legacy user-local launchers were preserved. Use /usr/local/bin/adminw21.'
