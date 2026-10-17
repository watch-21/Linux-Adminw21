#!/usr/bin/env bash
# Linux Adminw21 v1 - interactive operations; unsupported capabilities fail closed.
aw_present() { command -v "$1" >/dev/null 2>&1; }
aw_note() { lat_ui_notice "$1"; }
aw_input() { lat_ui_input "$1"; }
aw_confirm() { lat_ui_confirm "$(lat_t confirm_change): $1"; }
aw_view() { local output; output=$("$@" 2>&1); local rc=$?; lat_ui_show_text "${output:-No output} (exit: $rc)"; return 0; }
aw_exec() {
 local id=$1 preview=$2; shift 2
 aw_confirm "$preview" || return 0
 lat_privileged || return 1
 if "${LAT_PRIV[@]}" "$@"; then lat_log "$id" OK; aw_note "$(lat_t operation_success)"
 else lat_log "$id" FAILED; aw_note "$(lat_t operation_failed)"; return 1;fi
}
aw_need() { if ! aw_present "$1";then aw_note "$(lat_t missing): $1";return 1;fi; }
aw_menu() { local title=$1;shift; lat_ui_menu "$title" "$@" 0 "$(lat_t back)"; }
aw_file() { local p;p=$(aw_input "$(lat_t path_prompt)")||return 1;lat_validate_path "$p" || { aw_note "$(lat_t invalid_option)";return 1;};printf '%s\n' "$p"; }
aw_service() {
 aw_need systemctl || return
 local a name
 a=$(aw_menu "$(lat_t menu_06)" status Status start Start stop Stop restart Restart enable Enable disable Disable logs Logs failed Failed list List) || return
 [[ $a == 0 ]] && return
 case $a in failed) aw_view systemctl --failed --no-pager;return;;list) aw_view systemctl list-units --type=service --no-pager;return;;esac
 name=$(aw_input Service)||return
 [[ $name =~ ^[a-zA-Z0-9_.@:-]+$ ]] || { aw_note Invalid;return;}
 if [[ $a == status ]];then aw_view systemctl --no-pager status "$name";elif [[ $a == logs ]];then aw_need journalctl && aw_view journalctl -u "$name" -n 60 --no-pager
 else aw_exec SERVICE "systemctl $a $name" systemctl "$a" "$name";fi
}
aw_packages() {
 local op name
 op=$(aw_menu "$(lat_t menu_05)" update Update upgrade Upgrade install Install remove Remove search Search clean Clean) || return
 [[ $op == 0 ]] && return
 case $LAT_PKGMGR in
 apt)
  case $op in update) aw_exec PACKAGE 'apt-get update' apt-get update;;upgrade) aw_exec PACKAGE 'apt-get upgrade' apt-get upgrade;;clean) aw_exec PACKAGE 'apt-get autoremove' apt-get autoremove;;
  *) name=$(aw_input Package)||return;[[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9.+:_-]*$ ]]||return
    case $op in search) aw_view apt-cache search "$name";;install) aw_exec PACKAGE "Install $name" apt-get install "$name";;remove) aw_exec PACKAGE "Remove $name" apt-get remove "$name";;esac;;esac;;
 dnf|yum)
  local pm=$LAT_PKGMGR
  case $op in update|upgrade) aw_exec PACKAGE "$pm upgrade" "$pm" upgrade;;clean) aw_exec PACKAGE "$pm clean" "$pm" clean all;;
  *) name=$(aw_input Package)||return;[[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9.+:_-]*$ ]]||return
  case $op in search) aw_view "$pm" search "$name";; install|remove) aw_exec PACKAGE "$pm $op $name" "$pm" "$op" "$name";;esac;;esac;;
 pacman)
  case $op in update|upgrade) aw_exec PACKAGE 'pacman -Syu' pacman -Syu;;clean) aw_note 'Manual cache cleanup recommended';;
  *) name=$(aw_input Package)||return;[[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9.+_-]*$ ]]||return
   case $op in search) aw_view pacman -Ss "$name";;install) aw_exec PACKAGE "pacman -S $name" pacman -S "$name";;remove) aw_exec PACKAGE "pacman -R $name" pacman -R "$name";;esac;;esac;;
 zypper)
  case $op in update) aw_exec PACKAGE 'zypper refresh' zypper refresh;;upgrade) aw_exec PACKAGE 'zypper update' zypper update;;clean) aw_exec PACKAGE 'zypper clean' zypper clean;;
  *) name=$(aw_input Package)||return;[[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9.+_-]*$ ]]||return
  case $op in search) aw_view zypper search "$name";;install) aw_exec PACKAGE "Install $name" zypper install "$name";;remove) aw_exec PACKAGE "Remove $name" zypper remove "$name";;esac;;esac;;
 apk)
  case $op in update) aw_exec PACKAGE 'apk update' apk update;;upgrade) aw_exec PACKAGE 'apk upgrade' apk upgrade;;clean) aw_note 'Not available for APK';;
  *) name=$(aw_input Package)||return;[[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9.+_-]*$ ]]||return
  case $op in search) aw_view apk search "$name";;install) aw_exec PACKAGE "Install $name" apk add "$name";;remove) aw_exec PACKAGE "Remove $name" apk del "$name";;esac;;esac;;
 *) aw_note "$(lat_t compatibility_note): $LAT_PKGMGR";;
 esac
}
aw_permissions() {
 local a path value
 a=$(aw_menu "$(lat_t menu_04)" inspect Inspect mkdir Create-directory touch Create-file chmod Permissions chown Ownership copy Copy move Move delete Delete-file find Find-files grep Find-text) || return
 [[ $a == 0 ]] && return
 path=$(aw_file)||return
 case $a in
 inspect) aw_view ls -ld -- "$path";;mkdir) aw_exec FILE "mkdir $path" mkdir -p -- "$path";;touch) aw_exec FILE "touch $path" touch -- "$path";;
 chmod) value=$(aw_input 'Octal mode (e.g. 750)')||return;[[ $value =~ ^[0-7]{3,4}$ ]]||return;aw_exec FILE "chmod $value $path" chmod "$value" -- "$path";;
 chown) value=$(aw_input 'owner:group')||return;[[ $value =~ ^[a-z_][a-z0-9_-]*(:[a-z_][a-z0-9_-]*)?$ ]]||return;aw_exec FILE "chown $value $path" chown "$value" -- "$path";;
 copy|move) value=$(aw_file)||return;[[ $path != "$value" ]]||return;case $a in copy) aw_exec FILE "copy $path to $value" cp -n -- "$path" "$value";;move) aw_exec FILE "move $path to $value" mv -n -- "$path" "$value";;esac;;
 delete) [[ -f $path && ! -L $path ]]||{ aw_note 'Only regular files can be deleted here';return;};aw_exec FILE "DELETE FILE $path" rm -- "$path";;
 find) value=$(aw_input 'Filename glob (*.sh)')||return;aw_view find "$path" -name "$value";;
 grep) value=$(aw_input 'Text to search')||return;aw_view grep -RIn -- "$value" "$path";;esac
}
aw_network() {
 local a host iface
 a=$(aw_menu "$(lat_t menu_07)" interfaces Interfaces addresses Addresses routes Routes dns DNS listening Listening connections Connections ping Ping bandwidth Live-bandwidth processes Process-traffic peers Peer-bandwidth capture Packet-capture) ||return
 [[ $a == 0 ]]&&return
 case $a in
 interfaces|addresses) aw_need ip && aw_view ip -br addr;;routes) aw_need ip && aw_view ip route;;dns) if aw_present resolvectl;then aw_view resolvectl status;else aw_view cat /etc/resolv.conf;fi;;
 listening) aw_need ss && aw_view ss -tuln;;connections) aw_need ss && aw_view ss -tunap;;
 ping) host=$(aw_input Host)||return;[[ $host =~ ^[a-zA-Z0-9][a-zA-Z0-9.:-]{0,252}$ ]]||return;aw_need ping && aw_view ping -c 4 -W 2 "$host";;
 bandwidth) if [[ ${LAT_UI:-} == zenity ]]; then aw_note 'Live console monitor: use sudo adminw21 --terminal';return;fi;if aw_present nload;then iface=$(aw_input Interface)||return;[[ $iface =~ ^[a-zA-Z0-9_.:-]+$ ]]||return;nload "$iface";else aw_note 'Install nload for live bandwidth. Fallback: /proc/net/dev';aw_view cat /proc/net/dev;fi;;
 processes) if [[ ${LAT_UI:-} == zenity ]];then aw_note 'Run nethogs in terminal mode';return;fi;aw_need nethogs && { lat_privileged && "${LAT_PRIV[@]}" nethogs; };;
 peers) if [[ ${LAT_UI:-} == zenity ]];then aw_note 'Run iftop in terminal mode';return;fi;aw_need iftop && { lat_privileged && "${LAT_PRIV[@]}" iftop; };;
 capture) if [[ ${LAT_UI:-} == zenity ]];then aw_note 'Packet capture is terminal-only in this version';return;fi;aw_need tcpdump||return;iface=$(aw_input Interface)||return;[[ $iface =~ ^[a-zA-Z0-9_.:-]+$ ]]||return;aw_confirm "Capture 50 packets on $iface? Output may contain sensitive data"||return;lat_privileged||return;"${LAT_PRIV[@]}" tcpdump -i "$iface" -c 50 -nn;;esac
}
aw_monitor() { local a;a=$(aw_menu "$(lat_t menu_09)" dashboard Dashboard memory Memory disks Disks uptime Uptime top Top-processes load Load-health) ||return;case $a in dashboard) aw_dashboard;;memory) aw_view free -h;;disks) aw_view df -h;;uptime) aw_view uptime;;top) aw_view ps aux --sort=-%cpu;;load) aw_view cat /proc/loadavg;;esac; }
aw_storage() { local a;a=$(aw_menu "$(lat_t menu_12)" disks Disks mounts Mounts filesystems Filesystems inodes Inodes usage Directory-size)||return;case $a in disks) aw_view lsblk -f;;mounts) aw_view findmnt;;filesystems) aw_view df -Th;;inodes) aw_view df -i;;usage) local p;p=$(aw_file)||return;aw_view du -sh -- "$p";;esac; }
aw_logs() { aw_need journalctl||return;local a unit;a=$(aw_menu "$(lat_t menu_13)" recent Recent errors Errors service Service auth Auth-warnings)||return;case $a in recent) aw_view journalctl -n 75 --no-pager;;errors) aw_view journalctl -p err -n 75 --no-pager;;service) unit=$(aw_input Service)||return;[[ $unit =~ ^[a-zA-Z0-9_.@:-]+$ ]]||return;aw_view journalctl -u "$unit" -n 75 --no-pager;;auth) aw_view journalctl -p warning -n 75 --no-pager;;esac; }
aw_security() { local a;a=$(aw_menu "$(lat_t menu_10)" firewall Firewall-status ssh SSH-config-check sudo Sudo-access failed Failed-services ports Listening-ports)||return;case $a in firewall) if aw_present ufw;then aw_view ufw status;elif aw_present firewall-cmd;then aw_view firewall-cmd --state;else aw_note 'No supported firewall utility found';fi;;ssh) if aw_present sshd;then aw_view sshd -t;else aw_note 'sshd not installed';fi;;sudo) if aw_present sudo;then aw_view sudo -l;else aw_note 'sudo unavailable';fi;;failed) aw_need systemctl && aw_view systemctl --failed --no-pager;;ports) aw_need ss && aw_view ss -lntup;;esac; }
aw_processes() { local a pid;a=$(aw_menu "$(lat_t menu_06)" manager Process-manager list Processes top Top-CPU terminate Stop-process)||return;case $a in manager) aw_process_picker;;list) aw_view ps aux;;top) aw_view ps aux --sort=-%cpu;;terminate) pid=$(aw_input PID)||return;[[ $pid =~ ^[0-9]+$ ]]||return;((pid>1))||return;aw_process_terminate "$pid" TERM;;esac; }
aw_backup() {
 aw_need tar||return;local a src dest
 a=$(aw_menu "$(lat_t menu_08)" create Create-tar verify Verify-archive list List-archive restore Restore-archive)||return
 [[ $a == 0 ]]&&return
 case $a in
 create) src=$(aw_file)||return;[[ -d $src && $src != / ]]||return;dest=$(aw_file)||return;[[ $dest == *.tar.gz && ! -e $dest ]]||{ aw_note 'Use a new .tar.gz destination';return;};aw_confirm "Archive $src as $dest"||return;if tar -czf "$dest" -C "$(dirname -- "$src")" "$(basename -- "$src")";then lat_log BACKUP OK;aw_note 'Backup created';else lat_log BACKUP FAILED;aw_note 'Backup failed';fi;;
 verify|list) dest=$(aw_file)||return;[[ -f $dest ]]||return;if [[ $a == verify ]];then aw_view tar -tzf "$dest";else aw_view tar -tvzf "$dest";fi;;
 restore) dest=$(aw_file)||return;[[ -f $dest ]]||return;src=$(aw_file)||return;[[ -d $src && $src != / ]]||return;aw_confirm "Restore archive $dest into $src? May overwrite files"||return;aw_note 'Restore disabled in v1 until archive path validation is implemented; use manual tar inspection.';;esac
}
aw_cron() { local a line;a=$(aw_menu "$(lat_t menu_11)" show Show-current add Add-current)||return;[[ $a == 0 ]]&&return;aw_need crontab||return
 case $a in show) aw_view crontab -l;;add)
 line=$(aw_input 'Cron line (5 fields and absolute command)')||return
 # Reject dangerous shell metacharacters in this limited editor. Advanced syntax stays manual.
 [[ $line =~ ^[0-9*,-/]+[[:space:]]+[0-9*,-/]+[[:space:]]+[0-9*,-/]+[[:space:]]+[0-9*,-/]+[[:space:]]+[0-9*,-/]+[[:space:]]+/[a-zA-Z0-9_./-]+$ ]]||{ aw_note 'Invalid simple cron format';return;}
 aw_confirm "Add cron job: $line"||return
 local tmp;tmp=$(mktemp)||return;chmod 600 "$tmp";crontab -l >"$tmp" 2>/dev/null || :;printf '%s\n' "$line" >>"$tmp"
 if crontab "$tmp";then lat_log CRON OK;aw_note 'Added';else lat_log CRON FAILED;aw_note 'Failed';fi;rm -f -- "$tmp";;esac
}
aw_reports() { local a out;a=$(aw_menu "$(lat_t menu_14)" screen Screen-report save Save-TXT)||return;[[ $a == 0 ]]&&return
 local report;report="Linux Adminw21 v1 - $(date -Is)
Host: $(hostname)
OS: $LAT_DISTRO
Kernel: $(uname -r)
Uptime: $(uptime -p 2>/dev/null)

$(df -h 2>/dev/null)

$(free -h 2>/dev/null)"
 if [[ $a == screen ]];then lat_ui_show_text "$report";else out=$(aw_file)||return;[[ $out == *.txt && ! -e $out ]]||return;aw_confirm "Save report at $out"||return;printf '%s\n' "$report" >"$out"&&lat_log REPORT OK;fi
}
aw_module() {
 case $1 in
  4) aw_permissions;;5) aw_packages;;6) local selection;selection=$(aw_menu "$(lat_t menu_06)" 1 Services 2 Processes)||return;case $selection in 1)aw_service;;2)aw_processes;;esac;;
  7) aw_network;;8) aw_backup;;9) aw_monitor;;10) aw_security;;11) aw_cron;;12) aw_storage;;13) aw_logs;;14) aw_reports;;esac
}
