#!/bin/bash
set -Eeuo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
yes=no
while (($#));do
 case $1 in
  --help|-h)echo 'sudo ./uninstall.sh [--yes] [--destdir /staging/root]';exit 0;;
  --yes)yes=yes;;--destdir)shift;[[ $# -gt 0 ]] || exit 2;DESTDIR=$1;;
  *)exit 2;;
 esac
 shift
done
((EUID==0)) || exit 77
source "$ROOT/lib/install_paths.sh"
aw_install_base
aw_install_preflight
[[ -f $AW_DEST/.adminw21-owned ]] || { echo 'Owned installation not found';exit 2; }
if [[ $yes != yes ]];then
 read -r -p 'Uninstall application? Settings, logs and backups remain. [y/N]: ' answer
 [[ $answer == y || $answer == Y ]] || exit 0
fi
aw_install_snapshot
committed=no;moved=no
rollback() {
 local status=$?
 trap - EXIT
 if [[ $committed != yes ]];then
  set +e
  [[ $moved != yes ]] || mv -- "$AW_BACKUP/application" "$AW_DEST"
  aw_install_restore_registration || echo "Inspect $AW_BACKUP for recovery" >&2
 fi
 exit "$status"
}
trap rollback EXIT
for file in "${AW_FILES[@]}";do [[ ! -f $file ]] || rm -- "$file";done
mv -- "$AW_DEST" "$AW_BACKUP/application"
moved=yes;committed=yes
echo "Uninstalled. Application archived: $AW_BACKUP/application"
echo 'No configuration, logs, captures, backups or system packages were removed.'
