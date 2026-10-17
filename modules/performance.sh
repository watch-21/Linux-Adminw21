#!/usr/bin/env bash
# Linux Adminw21 v1 - system dashboard and safe process inspector
aw_language_is_de() { [[ ${LAT_LANGUAGE:-${LAT_LANG:-de}} == de ]]; }
aw_label() { if aw_language_is_de; then printf '%s' "$1"; else printf '%s' "$2";fi; }
aw_cpu_percent() {
 local idle1 idle2 total1 total2 delta_total delta_idle
 local first second
 first=$(head -n 1 /proc/stat); sleep 0.25; second=$(head -n 1 /proc/stat)
 read -r total1 idle1 < <(awk '{s=0;for(i=2;i<=9;i++)s+=$i;print s,$5+$6}' <<<"$first")
 read -r total2 idle2 < <(awk '{s=0;for(i=2;i<=9;i++)s+=$i;print s,$5+$6}' <<<"$second")
 delta_total=$((total2-total1));delta_idle=$((idle2-idle1))
 ((delta_total>0)) && printf '%s' "$(((delta_total-delta_idle)*100/delta_total))" || printf '0'
}
aw_metrics() {
 local cpu_count load mem_total mem_avail mem_used swap_total swap_free pct
 cpu_count=$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '?')
 load=$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || printf 'n/a')
 read -r mem_total mem_avail swap_total swap_free < <(awk '/^MemTotal:/ {m=$2} /^MemAvailable:/ {a=$2} /^SwapTotal:/ {s=$2} /^SwapFree:/ {f=$2} END {print m+0,a+0,s+0,f+0}' /proc/meminfo)
 mem_used=$((mem_total-mem_avail))
 ((mem_total>0)) && pct=$((mem_used*100/mem_total)) || pct=0
 printf '%s: %s\n' "$(aw_label 'Rechner' 'Host')" "$(hostname)"
 printf '%s: %s%% | %s: %s | %s: %s\n' "CPU" "$(aw_cpu_percent)" "$(aw_label 'CPU-Kerne' 'CPU cores')" "$cpu_count" "$(aw_label 'Last (1/5/15 Min.)' 'Load (1/5/15 min)')" "$load"
 printf '%s: %s%% (%s / %s MiB)\n' 'RAM' "$pct" "$((mem_used/1024))" "$((mem_total/1024))"
 printf '%s: %s / %s MiB\n' 'Swap' "$(((swap_total-swap_free)/1024))" "$((swap_total/1024))"
 if command -v df >/dev/null; then
   df -hP / 2>/dev/null | awk 'NR==2 {printf "Root disk: %s used / %s total (%s)\n",$3,$2,$5}'
 fi
 printf '%s: %s\n' "$(aw_label 'Laufzeit' 'Uptime')" "$(uptime -p 2>/dev/null || uptime)"
 printf '\n%s\n' "$(aw_label 'Prozesse (CPU)' 'Processes (CPU)')"
 ps -eo pid,ppid,user,stat,pcpu,pmem,comm --sort=-pcpu 2>/dev/null | head -n 13
}
aw_process_details() {
 local pid=$1
 [[ $pid =~ ^[0-9]+$ && -d /proc/$pid ]] || return 1
 ps -p "$pid" -o pid,ppid,user,uid,stat,pcpu,pmem,rss,etime,comm,args --no-headers 2>/dev/null
}
aw_process_starttime() {
 local pid=$1
 # /proc/PID/stat field 22, account for a command name containing spaces.
 [[ -r /proc/$pid/stat ]] || return 1
 sed 's/^.*) //' "/proc/$pid/stat" | awk '{print $20}'
}
aw_process_protected() {
 local pid=$1 current=$$ ppid steps=0 comm
 [[ $pid =~ ^[0-9]+$ ]] || return 0
 ((pid>2)) || return 0
 [[ -d /proc/$pid ]] || return 0
 comm=$(cat "/proc/$pid/comm" 2>/dev/null) || return 0
 case "$comm" in systemd|init|sshd|dbus-daemon|login|agetty) return 0;; esac
 # Do not kill the current process or its ancestor shell/terminal chain.
 while ((current>1 && steps<30)); do
   [[ $pid == "$current" ]] && return 0
   ppid=$(ps -o ppid= -p "$current" 2>/dev/null | tr -d ' ') || break
   [[ $ppid =~ ^[0-9]+$ ]] || break
   current=$ppid; ((steps+=1))
 done
 return 1
}
aw_process_terminate() {
 local pid=$1 signal=${2:-TERM} start new_start
 [[ $signal == TERM || $signal == KILL ]] || return 2
 if aw_process_protected "$pid"; then lat_ui_notice "$(aw_label 'Geschützter/ungültiger Prozess' 'Protected/invalid process')"; return 1;fi
 start=$(aw_process_starttime "$pid") || return 1
 lat_ui_show_text "$(aw_process_details "$pid")" || :
 lat_ui_confirm "$(aw_label 'Signal senden' 'Send signal') $signal -> PID $pid?" || return 1
 new_start=$(aw_process_starttime "$pid") || return 1
 [[ $start == "$new_start" ]] || { lat_ui_notice 'PID changed; cancelled';return 1; }
 if kill -s "$signal" "$pid"; then lat_log PROCESS OK;lat_ui_notice "$(aw_label 'Signal gesendet' 'Signal sent')";else lat_log PROCESS FAILED;lat_ui_notice "$(lat_t operation_failed)";return 1;fi
}
aw_process_picker() {
 local selected pid
 if [[ ${LAT_UI:-} == zenity ]]; then
   selected=$(ps -eo pid,user,pcpu,pmem,stat,comm --sort=-pcpu --no-headers | head -n 100 | awk '{print $1"|"$2"|"$3"|"$4"|"$5"|"$6}' | tr '\n' '\n' | while IFS='|' read -r pid user cpu mem stat cmd;do printf '%s\n' "$pid" "$user" "$cpu" "$mem" "$stat" "$cmd";done | zenity --list --title='Linux Adminw21 — Process Manager' --width=940 --height=650 --column=PID --column=USER --column='CPU %' --column='RAM %' --column=STATE --column=COMMAND --print-column=1) || return
   pid=$selected
 else
   lat_ui_show_text "$(ps -eo pid,user,pcpu,pmem,stat,comm --sort=-pcpu | head -n 35)"
   pid=$(lat_ui_input 'PID') || return
 fi
 [[ $pid =~ ^[0-9]+$ ]] || return
 selected=$(lat_ui_menu 'Process Manager' info "$(aw_label 'Details anzeigen' 'Show details')" term 'SIGTERM' force 'SIGKILL' 0 "$(aw_label 'Zurück' 'Back')") || return
 case $selected in info) lat_ui_show_text "$(aw_process_details "$pid")";;term) aw_process_terminate "$pid" TERM;;force) aw_process_terminate "$pid" KILL;;esac
}
aw_dashboard() {
 local selected
 while true; do
   selected=$(lat_ui_menu "Linux Adminw21 v1 — $(aw_label 'Systemübersicht' 'System dashboard')" overview "$(aw_label 'Systemzustand anzeigen' 'System overview')" processes "$(aw_label 'Prozesse verwalten' 'Process manager')" refresh "$(aw_label 'Aktualisieren' 'Refresh')" 0 "$(aw_label 'Zurück' 'Back')") || return
   case $selected in
     overview) lat_ui_show_text "$(aw_metrics)";;
     processes) aw_process_picker;;
     refresh) lat_ui_show_text "$(aw_metrics)";;
     0) return;;
   esac
 done
}
