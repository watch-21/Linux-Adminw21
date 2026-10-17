#!/bin/bash
# Administration implementation shared by Qt and the terminal action browser.
aw_name() { [[ ${1:-} =~ ^[a-z_][a-z0-9_-]{0,30}\$?$ ]]; }
aw_user() { aw_name "${1:-}" && getent passwd "$1" >/dev/null; }
aw_group() { aw_name "${1:-}" && getent group "$1" >/dev/null; }
aw_regular() {
 local uid minimum
 aw_user "$1" || return 1
 uid=$(id -u "$1") || return 1
 minimum=$(awk '$1=="UID_MIN" {print $2;exit}' /etc/login.defs 2>/dev/null);minimum=${minimum:-1000}
 [[ $uid =~ ^[0-9]+$ && $minimum =~ ^[0-9]+$ ]] || return 1
 ((uid>=minimum && uid!=65534)) && [[ $1 != root ]]
}
aw_path() {
 [[ ${1:-} == /* && $1 != / && $1 != *$'\n'* && $1 != *$'\r'* ]] || return 1
 local p=$1
 while [[ $p != / ]]; do [[ ! -L $p ]] || return 1;p=$(dirname -- "$p");done
 [[ $(realpath -m -- "$1") == "$1" ]]
}
aw_trusted_path() {
 aw_path "$1" || return 1
 local p
 p=$(dirname -- "$1")
 while [[ $p != / ]];do
  [[ -d $p && $(stat -c %u "$p") == 0 ]] || return 1
  # Sticky root-owned directories such as /tmp protect root-owned children.
  local mode;mode=$(stat -c %a "$p")
  if [[ $mode =~ [2367][0-9]$ || $mode =~ [2367]$ ]];then
   [[ $mode == 1??? ]] || return 1
   local child=$1
   [[ ! -e $child || $(stat -c %u "$child") == 0 ]] || return 1
  fi
  p=$(dirname -- "$p")
 done
}
aw_shell() { [[ ${1:-} == /* && -x $1 ]] && { grep -Fxq -- "$1" /etc/shells || [[ $1 == /usr/sbin/nologin || $1 == /sbin/nologin ]]; }; }
aw_systemd() { [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null; }
aw_unit() { [[ ${1:-} =~ ^[a-zA-Z0-9][a-zA-Z0-9_.@:-]*\.service$ ]]; }
aw_read_secret() {
 # read -d NUL detects embedded NUL rather than silently dropping it. EOF is
 # required after exactly one LF-terminated password record.
 if IFS= read -r -d '' AW_SECRET;then unset AW_SECRET;return 2;fi
 [[ $AW_SECRET == *$'\n' ]] || { unset AW_SECRET;return 2; }
 AW_SECRET=${AW_SECRET%$'\n'}
 [[ -n $AW_SECRET && ${#AW_SECRET} -le 4096 && $AW_SECRET != *$'\n'* && $AW_SECRET != *$'\r'* ]] || { unset AW_SECRET;return 2; }
}
aw_password() {
 local AW_SECRET
 aw_read_secret || return 2
 printf '%s:%s\n' "$1" "$AW_SECRET" | chpasswd >/dev/null 2>&1
 local rc=$?;unset AW_SECRET
 ((rc==0)) || { printf 'Password setting failed; account may remain locked. Use Change password.\n';return 1; }
}
aw_group_safe() {
 local gid minimum
 aw_group "$1" || return 1
 gid=$(getent group "$1" | cut -d: -f3)
 minimum=$(awk '$1=="GID_MIN"{print $2;exit}' /etc/login.defs 2>/dev/null);minimum=${minimum:-1000}
 ((gid>=minimum && gid!=65534)) && [[ $1 != sudo && $1 != wheel ]]
}
aw_process_protect() {
 local pid=$1 p=$$ parent comm
 [[ $pid =~ ^[0-9]+$ ]] && ((pid>2)) && [[ -r /proc/$pid/stat ]] || return 1
 comm=$(cat "/proc/$pid/comm") || return 1
 case "$comm" in systemd|init|sshd*|dbus-daemon|dbus-broker|login|agetty|sudo|pkexec|adminw21|NetworkManager|systemd-*|polkitd|cron|crond|runit|openrc-init|Xorg|Xwayland|gnome-shell|plasmashell|sddm|gdm*|lightdm|kwin_wayland) return 1;;esac
 [[ -n $(tr '\0' ' ' <"/proc/$pid/cmdline") ]] || return 1
 [[ $(tr '\0' ' ' <"/proc/$pid/cmdline") != *"$ROOT"* ]] || return 1
 while ((p>1));do [[ $p != "$pid" ]] || return 1;parent=$(awk '/^PPid:/{print $2}' "/proc/$p/status" 2>/dev/null);[[ $parent =~ ^[0-9]+$ ]] || break;p=$parent;done
}
aw_start() { sed 's/^.*) //' "/proc/$1/stat" | awk '{print $20}'; }
aw_package() {
 local op=$1 name=${2:-};lat_detect_distro
 case $op in install|remove|search|details) [[ -n $name ]] || return 2;;esac
 [[ -z $name || $name =~ ^[a-zA-Z0-9][a-zA-Z0-9.+:_/-]*$ && $name != *..* ]] || return 2
 if [[ -f /run/ostree-booted || -f /etc/NIXOS || $LAT_PKGMGR == nix ]];then aw_fail 'Immutable/NixOS package changes need dedicated workflows' 69;return;fi
 case "$LAT_PKGMGR:$op" in
 apt:search) apt-cache search -- "$name";;apt:details) apt-cache show -- "$name";;apt:list) dpkg-query -W;;apt:updates) apt list --upgradable 2>&1;;
 apt:clean) apt-get autoclean;;apt:autoremove) DEBIAN_FRONTEND=noninteractive apt-get -y autoremove;;
 apt:install|apt:remove) DEBIAN_FRONTEND=noninteractive apt-get -y "$op" -- "$name";;apt:refresh) apt-get update;;apt:upgrade) DEBIAN_FRONTEND=noninteractive apt-get -y upgrade;;
 dnf:search|yum:search|dnf:details|yum:details) local cmd=$op;[[ $cmd == details ]]&&cmd=info;"$LAT_PKGMGR" "$cmd" "$name";;
 dnf:clean|yum:clean) "$LAT_PKGMGR" clean all;;
 dnf:list|yum:list) "$LAT_PKGMGR" list --installed;;dnf:updates|yum:updates) "$LAT_PKGMGR" list --upgrades;;
 dnf:install|dnf:remove|yum:install|yum:remove) "$LAT_PKGMGR" -y "$op" "$name";;dnf:refresh|yum:refresh) "$LAT_PKGMGR" makecache;;dnf:upgrade|yum:upgrade) "$LAT_PKGMGR" -y upgrade;;
 pacman:search) pacman -Ss -- "$name";;pacman:details) pacman -Si -- "$name";;pacman:list) pacman -Q;;pacman:updates) local output rc;output=$(pacman -Qu 2>&1);rc=$?;if ((rc==1)) && [[ -z $output ]];then echo "No updates in local package metadata";return 0;fi;printf '%s\n' "$output";return "$rc";;pacman:install) pacman --noconfirm -S -- "$name";;pacman:remove) pacman --noconfirm -R -- "$name";;pacman:upgrade) pacman --noconfirm -Syu;;pacman:refresh) aw_fail 'Standalone sync risks partial upgrades; use Upgrade (pacman -Syu)' 69;;
 zypper:clean) zypper --non-interactive clean;;
 zypper:search) zypper search -- "$name";;zypper:details) zypper info -- "$name";;zypper:list) zypper search -i;;zypper:updates) zypper list-updates;;zypper:refresh) zypper --non-interactive refresh;;zypper:upgrade) zypper --non-interactive update;;zypper:install|zypper:remove) zypper --non-interactive "$op" -- "$name";;
 apk:search) apk search "$name";;apk:details) apk info -a "$name";;apk:list) apk info;;apk:updates) apk version -l '<';;apk:install) apk add "$name";;apk:remove) apk del "$name";;apk:refresh) apk update;;apk:upgrade) apk upgrade;;
 xbps:search) xbps-query -Rs "$name";;xbps:details) xbps-query -R "$name";;xbps:list) xbps-query -l;;xbps:updates) xbps-install -un;;xbps:install) xbps-install -y "$name";;xbps:remove) xbps-remove -y "$name";;xbps:refresh) xbps-install -S;;xbps:upgrade) xbps-install -yu;;
 portage:search) emerge --search "$name";;portage:details) emerge --info "$name";;portage:list) find /var/db/pkg -mindepth 2 -maxdepth 2 -type d;;portage:updates) emerge -puD @world;;portage:install) emerge -- "$name";;portage:remove) emerge --unmerge -- "$name";;portage:refresh) emerge --sync;;portage:upgrade) emerge -uD @world;;
 *) aw_fail "Unavailable package action: $LAT_PKGMGR/$op" 69;;esac
}
aw_cron_edit() {
 local op=$1 user=$2 digest=$3 value=${4:-} tmp current index schedule command
 aw_regular "$user" || return 2
 command -v crontab >/dev/null || return 69
 tmp=$(mktemp);chmod 600 "$tmp"
 # All clients serialize edits. This also catches edits by external clients.
 exec 9>/run/adminw21-cron.lock;flock -x 9 || { rm -f "$tmp";return 1; }
 if ! crontab -u "$user" -l >"$tmp" 2>"$tmp.err";then
  grep -q 'no crontab for' "$tmp.err" || { cat "$tmp.err";rm -f "$tmp" "$tmp.err";return 1; }
 fi
 rm -f "$tmp.err"
 current=$(sha256sum "$tmp" | cut -d' ' -f1)
 [[ $digest == "$current" ]] || { rm -f "$tmp";aw_fail 'Crontab changed; reload before editing';return; }
 if [[ $op == add ]];then
  schedule=${value%|*};command=${value##*|}
  schedule=$(/usr/bin/python3 -I "$ROOT/backend/protocol.py" cron "$schedule") || { rm -f "$tmp";return 2; }
  # Fixed permitted tasks; no arbitrary root-shell execution surface.
  case "$command" in /usr/bin/true|'/usr/local/bin/adminw21 --health') ;;*)rm -f "$tmp";return 2;;esac
  printf '%s %s # adminw21\n' "$schedule" "$command" >>"$tmp"
 else
  index=${value%%|*};[[ $index =~ ^[0-9]+$ ]] || { rm -f "$tmp";return 2; }
  local line
  line=$(sed -n "${index}p" "$tmp")
  [[ $line == *' # adminw21' ]] || { rm -f "$tmp";aw_fail 'Only application-owned entries may be edited';return; }
  case $op in
  delete) sed -i "${index}d" "$tmp";;
  toggle) if [[ $line == '# disabled '* ]];then sed -i "${index}s/^# disabled //" "$tmp";else sed -i "${index}s/^/# disabled /" "$tmp";fi;;
  edit) schedule=${value#*|};schedule=$(/usr/bin/python3 -I "$ROOT/backend/protocol.py" cron "$schedule") || { rm -f "$tmp";return 2; };command=${line#* };command=${line##*|};
   # Preserve the owned executable; replace only the five schedule fields.
   command=$(awk '{for(i=6;i<=NF;i++)printf "%s%s",$i,(i<NF?" ":"\n")}' <<<"${line#\# disabled }")
   sed -i "${index}d" "$tmp";printf '%s %s\n' "$schedule" "$command" >>"$tmp";;
  *)rm -f "$tmp";return 2;;esac
 fi
 crontab -u "$user" "$tmp";local rc=$?;rm -f "$tmp";return "$rc"
}
aw_observe() {
 local label=$1;shift
 printf '\n--- %s ---\n' "$label"
 if ! command -v "$1" >/dev/null;then
  printf '[UNAVAILABLE] %s\n' "$1";((AW_READ_FAILURES+=1));return 0
 fi
 "$@";local status=$?
 if ((status==0));then echo '[OK]';else printf '[FAILED: %s]\n' "$status";((AW_READ_FAILURES+=1));fi
 return 0
}
aw_dispatch() {
 local action=$1;shift
 local name=${1:-} value=${2:-} third=${3:-} fourth=${4:-}
 case "$action" in
 capabilities) lat_detect_distro;printf 'Distribution: %s\nPackage manager: %s\n' "$LAT_DISTRO" "$LAT_PKGMGR";if aw_systemd;then echo 'Init: systemd';else echo 'Init: non-systemd (service management unavailable)';fi
 for name in python3 pkexec ip ss tar rsync crontab tcpdump nload iftop nethogs vnstat tshark;do
  local path
  if path=$(command -v "$name");then printf '%s: %s\n' "$name" "$path";else printf '%s: unavailable\n' "$name";fi
 done;;
 sessions.list) /usr/bin/python3 -I "$ROOT/backend/sessions.py";;
 users.list) local minimum;minimum=$(awk '$1=="UID_MIN"{print $2;exit}' /etc/login.defs 2>/dev/null);printf 'UID_MIN=%s\n' "${minimum:-1000}";getent passwd;;
 users.info) aw_user "$name" || return 2;getent passwd "$name";id "$name";if ! passwd -S "$name" 2>/dev/null;then echo 'Password status unavailable to this caller';fi;;
 groups.list) getent group;;
 groups.info) aw_group "$name" || return 2;getent group "$name";local gid;gid=$(getent group "$name"|cut -d: -f3);printf 'Primary members:\n';getent passwd|awk -F: -v gid="$gid" '$4==gid{print $1}';;
 user.create)
  [[ $# == 6 ]] && aw_name "$name" && ! getent passwd "$name" >/dev/null && aw_shell "$third" || return 2
  local args=(-M -s "$third") group
  [[ $value == yes || $value == no ]] || return 2
  [[ $value == yes ]]&&args[0]=-m
  if [[ -n $fourth ]];then aw_group "$fourth" || return 2;args+=(-g "$fourth");fi
  local groups=$5 admin=$6
  if [[ -n $groups ]];then IFS=, read -ra values <<<"$groups";for group in "${values[@]}";do aw_group "$group" || return 2;done;fi
  [[ $admin == yes || $admin == no ]] || return 2
  if [[ $admin == yes ]];then if aw_group sudo;then group=sudo;elif aw_group wheel;then group=wheel;else return 69;fi;groups=${groups:+$groups,}$group;fi
  [[ -z $groups ]]||args+=(-G "$groups")
  # Validate/consume the entire protected input before creating anything.
  local AW_SECRET
  aw_read_secret || return 2
  useradd "${args[@]}" -- "$name" || { unset AW_SECRET;return 1; }
  if ! printf '%s\n' "$AW_SECRET" | aw_password "$name";then unset AW_SECRET;printf 'PARTIAL: user created, password not set.\n';return 10;fi
  unset AW_SECRET;echo 'User created and password set';;
 user.password) [[ $# == 1 ]]&&aw_regular "$name" || return 2;aw_password "$name";;
 user.delete) [[ $# == 2 ]]&&aw_regular "$name" || return 2
  case $value in keep) userdel -- "$name";;remove) local home;home=$(getent passwd "$name" | cut -d: -f6);[[ $home == "/home/$name" ]]&&aw_path "$home" || return 2;userdel -r -- "$name";;*)return 2;;esac;;
 user.lock|user.unlock) aw_regular "$name" || return 2;local flag=-L;[[ $action == user.unlock ]]&&flag=-U;usermod "$flag" -- "$name";;
 user.shell) aw_regular "$name"&&aw_shell "$value" || return 2;usermod -s "$value" -- "$name";;
 user.primary) aw_regular "$name"&&aw_group "$value" || return 2;usermod -g "$value" -- "$name";;
 user.home) aw_regular "$name" || return 2;[[ $value == "/home/$name" && ! -e $value ]]&&aw_path "$value" || return 2;usermod -d "$value" -m -- "$name";;
 user.ssh.add|user.ssh.remove)
  aw_regular "$name" || return 2
  [[ $value =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521))[[:space:]][A-Za-z0-9+/=]+([[:space:]][^[:cntrl:]]*)?$ ]] || return 2
  local home;home=$(getent passwd "$name"|cut -d: -f6);[[ $home == "/home/$name" ]] || return 2
  command -v runuser >/dev/null || return 69
  runuser -u "$name" -- "$ROOT/backend/ssh-key.sh" "$home" "$value" "${action##*.}";;
 group.create) aw_name "$name" || return 2;groupadd -- "$name";;group.delete) aw_group_safe "$name" || return 2;groupdel -- "$name";;
 group.add|group.remove) aw_regular "$name"&&aw_group "$value" || return 2;[[ $(id -gn "$name") != "$value" ]] || return 2
 if [[ $action == group.add ]];then usermod -aG "$value" -- "$name";else gpasswd -d "$name" "$value";fi;;
 process.signal) [[ $# == 3 && $value =~ ^[0-9]+$ && ( $third == TERM || $third == KILL ) ]]&&aw_process_protect "$name" || return 2
  [[ $(aw_start "$name") == "$value" ]] || { aw_fail 'Process exited or PID reused';return; }
  kill -s "$third" "$name" || return 1
  if [[ ! -d /proc/$name ]];then echo 'Signal sent; process exited';else echo 'Signal sent; exit is not yet confirmed';fi;;
 services.list) aw_systemd || { aw_fail 'systemd not running' 69;return; };systemctl list-units --all --type=service --no-pager --plain;;
 services.logs) aw_systemd&&aw_unit "$name" || return 69;journalctl -u "$name" -n 200 --no-pager;;
 service.*) aw_systemd&&aw_unit "$name" || return 69
  case ${action#service.} in
  stop|disable|restart)
   case $name in ssh*.service|NetworkManager*.service|networking.service|systemd-*.service|dbus*.service|polkit.service)
    aw_fail 'Essential/remote-access service protected';return;;esac;;esac
  systemctl "${action#service.}" "$name";;
 packages.*|package.*) aw_package "${action#*.}" "$name";;
 network.ping) [[ $name =~ ^[a-zA-Z0-9:][a-zA-Z0-9.:-]{0,252}$ ]]||return 2;ping -c 4 -W 2 -- "$name";;
 network.info) local AW_READ_FAILURES=0
  aw_observe 'Interfaces' ip -s addr
  aw_observe 'IPv4 routes' ip route
  aw_observe 'IPv6 routes' ip -6 route
  aw_observe 'DNS' cat /etc/resolv.conf
  aw_observe 'Sockets' ss -tunap
  ((AW_READ_FAILURES==0)) || return 10;;
 storage.info) local AW_READ_FAILURES=0
  aw_observe 'Disks' lsblk -f
  aw_observe 'Mounts' findmnt
  aw_observe 'Filesystems' df -Th
  aw_observe 'Inodes' df -i
  ((AW_READ_FAILURES==0)) || return 10;;
 files.list) aw_path "$name" || return 2;ls -la -- "$name";;
 files.size) aw_path "$name" || return 2;du -x -h --max-depth=1 -- "$name";;
 files.find) aw_path "$name"&&[[ -n $value && $value != *$'\n'* ]] || return 2;find -P "$name" -xdev -name "$value" -print;;
 files.search) aw_path "$name"&&[[ -n $value ]] || return 2;grep -rIn -- "$value" "$name";;
 file.*) aw_trusted_path "$name" || { aw_fail "Path must have root-controlled parents; symbolic links are refused";return; }
  case ${action#file.} in
  mkdir) mkdir -- "$name";;touch) [[ ! -e $name ]]||return 2;touch -- "$name";;
  chmod) [[ $value =~ ^[0-7]{3}$ && -e $name ]] || return 2;chmod "$value" -- "$name";;
  chown) [[ $value =~ ^[a-z_][a-z0-9_-]*:[a-z_][a-z0-9_-]*$ ]]||return 2;aw_user "${value%:*}"&&aw_group "${value#*:}" || return 2;chown "$value" -- "$name";;
  copy) [[ -f $name && ! -e $value ]]&&aw_trusted_path "$value" || return 2;cp -n -- "$name" "$value";;
  move) [[ -f $name && ! -e $value ]]&&aw_trusted_path "$value" || return 2;mv -n -- "$name" "$value";;
  delete) [[ -f $name && $(stat -c %h "$name") == 1 ]]||return 2;rm -- "$name";;*)return 2;;esac;;
 backup.create) [[ -d $name ]]&&aw_path "$name"&&aw_trusted_path "$value"&&[[ $value == *.tar.gz && ! -e $value && $value != "$name/"* ]]||return 2
  local tmp;tmp=$(mktemp "$(dirname -- "$value")/.backup.XXXXXXXX")||return 1
  if tar --one-file-system -czf "$tmp" -C "$(dirname -- "$name")" -- "$(basename -- "$name")" && /usr/bin/python3 -I "$ROOT/backend/protocol.py" archive "$tmp" >/dev/null;then
   chmod 600 "$tmp";ln -- "$tmp" "$value";local rc=$?;rm -f "$tmp";return "$rc"
  else rm -f "$tmp";aw_fail 'Backup failed or contains unsupported links. Source preserved' 1;fi;;
 backup.list) aw_path "$name" || return 2;find -P "$name" -maxdepth 1 -type f -name '*.tar.gz' -printf '%f\t%s bytes\t%TY-%Tm-%Td\n';;
 backup.verify|backup.preview) aw_path "$name"&&[[ -f $name ]]||return 2;/usr/bin/python3 -I "$ROOT/backend/protocol.py" archive "$name";;
 backup.restore) aw_path "$name"&&aw_trusted_path "$value"&&[[ -f $name && -d $value && $(stat -c %u "$value") == 0 && ! $(stat -c %a "$value") =~ [2367][0-9]$ && ! $(stat -c %a "$value") =~ [2367]$ && -z $(ls -A -- "$value") ]]||return 2
  # Restore only to an empty isolated directory. Snapshot first so validation and
  # extraction consume identical bytes even if the source archive is replaced.
  local tmp;tmp=$(mktemp)||return 1;cp -- "$name" "$tmp"||{ rm -f "$tmp";return 1; }
  if /usr/bin/python3 -I "$ROOT/backend/protocol.py" archive "$tmp" >/dev/null;then tar -xzf "$tmp" -C "$value" --no-same-owner --no-same-permissions --keep-old-files;local rc=$?;else local rc=2;fi
  rm -f "$tmp";return "$rc";;
 backup.retention)
  aw_trusted_path "$name" && [[ -d $name && $value =~ ^[0-9]+$ ]] && ((value>=1 && value<=1000)) || return 2
  local files=() f count=0 listing
  # Only files with application-generated names are eligible; never generic archives.
  # Check discovery errors before pruning, including on systems without /dev/fd.
  listing=$(mktemp) || return 1
  if ! (set -o pipefail;find -P "$name" -maxdepth 1 -type f -name 'adminw21-[0-9]*.tar.gz' -printf '%f\0' | sort -zr) >"$listing";then
   rm -f -- "$listing";return 1
  fi
  if ! mapfile -d '' files <"$listing";then rm -f -- "$listing";return 1;fi
  rm -f -- "$listing"
  for f in "${files[@]}";do
   [[ $f =~ ^adminw21-[0-9]{8}T[0-9]{6}Z-[0-9]+\.tar\.gz$ ]] || continue
   [[ $(stat -c %u "$name/$f") == 0 && $(stat -c %h "$name/$f") == 1 ]] || continue
   ((count+=1));if ((count>value));then
    rm -- "$name/$f" || return 1;printf 'Removed: %s\n' "$f"
   fi
  done;;
 backup.schedule)
  aw_path "$name" && [[ -d $name ]] && aw_trusted_path "$value" && [[ -d $value && $name != "$value" && $value != "$name/"* ]] || return 2
  local schedule job
  schedule=$(/usr/bin/python3 -I "$ROOT/backend/protocol.py" cron "$third") || return 2
  command -v crontab >/dev/null && [[ -d /etc/cron.d ]] || return 69
  [[ ! -L /etc/adminw21 && ! -L /etc/adminw21/jobs && ! -L /etc/cron.d && ! -L /var/log/adminw21 ]] || return 2
  install -d -m 700 /etc/adminw21/jobs /var/log/adminw21
  job=$(date -u +%Y%m%d%H%M%S)-$$
  printf '%s\n%s\n' "$name" "$value" >"/etc/adminw21/jobs/$job"
  chmod 600 "/etc/adminw21/jobs/$job"
  printf '%s root /usr/local/share/adminw21/backend/backend.sh backup.run %s >>/var/log/adminw21/backup.log 2>&1\n' "$schedule" "$job" >"/etc/cron.d/adminw21-$job"
  chmod 644 "/etc/cron.d/adminw21-$job"
  printf 'Scheduled job: %s; log: /var/log/adminw21/backup.log\n' "$job";;
 backup.schedule.remove)
  [[ $name =~ ^[0-9]{14}-[0-9]+$ && -f /etc/adminw21/jobs/$name && ! -L /etc/adminw21/jobs/$name && ! -L /etc/cron.d/adminw21-$name ]] || return 2
  rm -- "/etc/cron.d/adminw21-$name" "/etc/adminw21/jobs/$name";;
 backup.run)
  [[ $name =~ ^[0-9]{14}-[0-9]+$ && -f /etc/adminw21/jobs/$name && ! -L /etc/adminw21/jobs/$name && $(stat -c %u "/etc/adminw21/jobs/$name") == 0 ]] || return 2
  local paths=();mapfile -t paths <"/etc/adminw21/jobs/$name"
  [[ ${#paths[@]} == 2 ]] || return 2
  aw_dispatch backup.create "${paths[0]}" "${paths[1]}/adminw21-$(date -u +%Y%m%dT%H%M%SZ)-$$.tar.gz";;
 cron.list)
  aw_user "$name"||return 2
  command -v crontab >/dev/null || return 69
  if ((EUID!=0)) && [[ $name != "$(id -un)" ]];then aw_fail 'Reading another user crontab requires administrator authentication' 77;return;fi
  local tmp rc args=();tmp=$(mktemp)||return 1
  if ((EUID==0));then args=(-u "$name");fi
  crontab "${args[@]}" -l >"$tmp" 2>"$tmp.err";rc=$?
  if ((rc!=0));then
   if grep -q 'no crontab for' "$tmp.err";then rc=0
   else cat "$tmp.err";rm -f "$tmp" "$tmp.err";return "$rc";fi
  fi
  printf 'Revision: ';sha256sum "$tmp"|cut -d' ' -f1
  cat -n "$tmp";rm -f "$tmp" "$tmp.err";return "$rc";;
 cron.add|cron.edit|cron.toggle|cron.delete) aw_cron_edit "${action#cron.}" "$name" "$value" "$third";;
 logs.search) [[ -z $name ]]||aw_unit "$name"||return 2;local args=(-n 300 --no-pager);[[ -z $name ]]||args+=(-u "$name");[[ -z $value ]]||args+=(--grep "$value");journalctl "${args[@]}";;
 security.inspect) local AW_READ_FAILURES=0
  aw_observe 'SSH effective configuration' sshd -T
  if command -v ufw >/dev/null;then aw_observe 'Firewall' ufw status verbose
  elif command -v firewall-cmd >/dev/null;then aw_observe 'Firewall' firewall-cmd --list-all
  else printf '\nFirewall: unavailable\n';((AW_READ_FAILURES+=1));fi
  aw_observe 'Listening ports' ss -lntup
  aw_observe 'Failed logins' lastb -n 20
  printf '\nAdministrative group membership (not a sudo authorization check)\n'
  getent group sudo || :;getent group wheel || :
  if aw_systemd;then aw_observe 'Failed services' systemctl --failed --no-pager
  else echo 'Failed services: systemd unavailable';fi
  ((AW_READ_FAILURES==0)) || return 10;;
 firewall.add|firewall.remove)
  # Add/remove only a tagged inbound allow rule, never change default policies.
  [[ $name =~ ^[1-9][0-9]{0,4}$ ]]&&((name>=1 && name<=65535))&&[[ $value == tcp || $value == udp ]]||return 2
  [[ $name != 22 ]]||{ aw_fail 'SSH port is protected';return; }
  command -v ufw >/dev/null||return 69
  if [[ $action == firewall.add ]];then ufw allow "$name/$value" comment adminw21;else
   local rules;rules=$(ufw status numbered) || return 1
   local indices=() index
   mapfile -t indices < <(printf '%s\n' "$rules" | /usr/bin/python3 -I "$ROOT/backend/firewall_rules.py" "$name" "$value")
   ((${#indices[@]})) || { aw_fail 'No exact application-owned allow rule';return; }
   for index in "${indices[@]}";do
    [[ $index =~ ^[0-9]+$ ]] || return 2
    ufw --force delete "$index" || return 1
   done
  fi;;
 capture.start)
  [[ $name =~ ^[a-zA-Z0-9_.:-]+$ && -d /sys/class/net/$name && $value =~ ^[0-9]+$ && $third =~ ^[0-9]+$ ]]||return 2
  ((value>=1 && value<=600 && third>=1 && third<=100000))||return 2
  [[ $fourth != -* && $fourth != *$'\n'* ]]||return 2
  command -v tcpdump >/dev/null&&command -v timeout >/dev/null||return 69
  [[ ! -L /var/lib/adminw21 && ! -L /var/lib/adminw21/captures ]]||return 2
  install -d -m 700 /var/lib/adminw21/captures
  local out
  out="/var/lib/adminw21/captures/$(date +%s)-$$.pcap"
  printf 'Destination: %s (root-only); duration %ss; maximum 10 MB\n' "$out" "$value"
  [[ ! -L /run/adminw21 ]]||return 2
  install -d -m 700 /run/adminw21
  exec 8>/run/adminw21/capture.lock
  flock -n 8 || { aw_fail 'A capture is already running';return; }
  tcpdump -Z root -i "$name" -nn -c "$third" -C 10 -W 1 -w "$out" -- "$fourth" &
  local pid=$! start owner=${PKEXEC_UID:-0} rc begin=$SECONDS
  sleep .05
  start=$(aw_start "$pid")||{ wait "$pid";return $?; }
  printf '%s\n%s\n%s\n' "$pid" "$start" "$owner" >/run/adminw21/capture.state
  while kill -0 "$pid" 2>/dev/null;do
   [[ $(aw_start "$pid" 2>/dev/null) == "$start" ]]||break
   if ((SECONDS-begin>=value));then kill -INT "$pid";break;fi
   sleep .2
  done
  wait "$pid";rc=$?
  rm -f /run/adminw21/capture.state
  chmod 600 "$out"* 2>/dev/null || :
  return "$rc";;
 capture.stop)
  [[ -f /run/adminw21/capture.state && ! -L /run/adminw21/capture.state && $(stat -c %u /run/adminw21/capture.state) == 0 ]]||return 2
  local state=();mapfile -t state </run/adminw21/capture.state
  [[ ${#state[@]} == 3 && ${state[0]} =~ ^[0-9]+$ && ${state[1]} =~ ^[0-9]+$ && ${state[2]} == "${PKEXEC_UID:-0}" ]] || return 77
  [[ $(cat "/proc/${state[0]}/comm") == tcpdump && $(aw_start "${state[0]}") == "${state[1]}" ]]||return 2
  kill -INT "${state[0]}";echo 'Stop requested; capture will report its final status';;
 *)return 2;;esac
}
