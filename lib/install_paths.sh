#!/bin/bash
# Installation-only helpers. DESTDIR stages a package, never changes runtime paths.
aw_install_base() {
 AW_BASE=${DESTDIR:-}
 [[ -z $AW_BASE || $AW_BASE == /* && $AW_BASE != / && $AW_BASE != *$'\n'* ]] || return 2
 if [[ -n $AW_BASE ]];then
  [[ $(realpath -m -- "$AW_BASE") == "$AW_BASE" ]] || return 2
  local p=$AW_BASE child=$AW_BASE mode
  [[ -d $AW_BASE ]] || return 2
  while [[ $p != / ]];do
   [[ ! -L $p && -d $p && $(stat -c %u "$p") == 0 ]] || return 2
   mode=$(stat -c %a "$p")
   if [[ $mode =~ [2367][0-9]$ || $mode =~ [2367]$ ]];then
    [[ $mode == 1??? && $(stat -c %u "$child") == 0 ]] || return 2
   fi
   child=$p;p=$(dirname -- "$p")
  done
 fi
 AW_DEST="$AW_BASE/usr/local/share/adminw21"
 AW_LAUNCHER="$AW_BASE/usr/local/bin/adminw21"
 AW_FILES=("$AW_LAUNCHER" "$AW_BASE/usr/share/applications/adminw21.desktop" "$AW_BASE/usr/share/applications/adminw21-terminal.desktop" "$AW_BASE/usr/share/polkit-1/actions/org.adminw21.backend.policy")
}
aw_install_owned() {
 local file=$1 kind=$2
 [[ ! -L $file ]] || return 1
 [[ ! -e $file ]] && return 0
 [[ -f $file && $(stat -c %u "$file") == 0 ]] || return 1
 case $kind in
  0)grep -Fq 'share/adminw21/admin.sh' "$file";;
  1)grep -Fxq 'Exec=/usr/local/bin/adminw21 --gui' "$file";;
  2)grep -Fxq 'Exec=sudo /usr/local/bin/adminw21 --terminal' "$file";;
  3)grep -Fq '<action id="org.adminw21.backend">' "$file";;
  *)return 1;;
 esac
}
aw_install_preflight() {
 local p mode index
 for p in "$AW_BASE/usr" "$AW_BASE/usr/local" "$AW_BASE/usr/local/share" "$AW_BASE/usr/local/bin" "$AW_BASE/usr/share" "$AW_BASE/usr/share/applications" "$AW_BASE/usr/share/polkit-1" "$AW_BASE/usr/share/polkit-1/actions" "$AW_BASE/var" "$AW_BASE/var/backups" "$AW_BASE/var/backups/adminw21";do
  [[ ! -L $p ]] || { echo "Unsafe symlink: $p" >&2;return 2; }
  if [[ -e $p ]];then
   [[ -d $p && $(stat -c %u "$p") == 0 ]] || return 2
   mode=$(stat -c %a "$p")
   [[ ! $mode =~ [2367][0-9]$ && ! $mode =~ [2367]$ ]] || { echo "Unsafe directory: $p" >&2;return 2; }
  fi
 done
 [[ ! -L $AW_DEST ]] || return 2
 if [[ -e $AW_DEST ]];then
  [[ -d $AW_DEST && -f $AW_DEST/admin.sh && ! -L $AW_DEST/admin.sh && $(stat -c %u "$AW_DEST") == 0 ]] || return 2
  if [[ -f $AW_DEST/.adminw21-owned ]];then
   [[ $(cat "$AW_DEST/.adminw21-owned") == 'Linux Adminw21 v1' ]] || return 2
  else grep -Fq 'Linux Adminw21' "$AW_DEST/admin.sh" || return 2;fi
 fi
 for index in "${!AW_FILES[@]}";do
  aw_install_owned "${AW_FILES[index]}" "$index" || { echo "Unknown registration: ${AW_FILES[index]}" >&2;return 2; }
 done
}
aw_install_atomic() {
 local source=$1 target=$2 mode=$3 temporary
 temporary=$(mktemp "$(dirname -- "$target")/.adminw21-write.XXXXXXXX") || return 1
 if install -m "$mode" -- "$source" "$temporary" && mv -fT -- "$temporary" "$target";then return 0;fi
 rm -f -- "$temporary";return 1
}
aw_install_snapshot() {
 install -d -m 700 -- "$AW_BASE/var/backups/adminw21"
 AW_BACKUP=$(mktemp -d "$AW_BASE/var/backups/adminw21/transaction-$(date -u +%Y%m%dT%H%M%SZ).XXXXXXXX") || return 1
 install -d -m 700 -- "$AW_BACKUP/registration"
 local index
 for index in "${!AW_FILES[@]}";do
  if [[ -f ${AW_FILES[index]} ]];then cp -p -- "${AW_FILES[index]}" "$AW_BACKUP/registration/$index";fi
 done
}
aw_install_restore_registration() {
 local index file
 for index in "${!AW_FILES[@]}";do
  file=${AW_FILES[index]}
  if [[ -f $AW_BACKUP/registration/$index ]];then
   aw_install_atomic "$AW_BACKUP/registration/$index" "$file" "$(stat -c %a "$AW_BACKUP/registration/$index")" || return 1
  elif [[ -e $file ]];then
   aw_install_owned "$file" "$index" || return 1
   rm -- "$file" || return 1
  fi
 done
}
