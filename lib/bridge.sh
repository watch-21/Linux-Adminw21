#!/bin/bash
# Shared backend terminal browser. Existing dialog/whiptail/plain helpers stay.
lat_backend_call() { "$LAT_ROOT/backend/backend.sh" "$@"; }
lat_backend_show() {
 local response rc
 response=$(lat_backend_call "$@");rc=$?
 lat_ui_show_text "$(printf '%s' "$response" | python3 -c 'import json,sys;r=json.load(sys.stdin);print(("OK" if r["ok"] else "FAILED")+": "+r["output"])')"
 return "$rc"
}
lat_shared_action() {
 local action=$1 meta privilege label default answer p1 p2 response rc
 local args=() fields=()
 mapfile -t fields < <(python3 -I "$LAT_ROOT/gui/catalog.py" fields "$LAT_LANGUAGE" "$action")
 privilege=${fields[0]}
 for meta in "${fields[@]:1}";do
  label=${meta%%$'\t'*};default=${meta#*$'\t'}
  # Empty optional arguments must be possible; this input helper returns empty.
  answer=$(lat_ui_optional_input "$label [$default]") || return
  [[ -n $answer ]]||answer=$default
  args+=("$answer")
 done
 if [[ $privilege == yes ]];then lat_ui_confirm "$action: ${args[*]}" || return;fi
 case $action in
 user.create|user.password)
  p1=$(lat_ui_secret 'Password') || return
  p2=$(lat_ui_secret 'Confirm password') || { unset p1;return; }
  [[ -n $p1 && $p1 == "$p2" && $p1 != *$'\n'* && $p1 != *$'\r'* ]] || { unset p1 p2;lat_ui_notice 'Password confirmation invalid';return; }
  response=$(printf '%s\n' "$p1" | lat_backend_call "$action" "${args[@]}");rc=$?
  unset p1 p2
  lat_ui_show_text "$(printf '%s' "$response" | python3 -c 'import json,sys;r=json.load(sys.stdin);print(r["output"])')"
  return "$rc";;
 *)lat_backend_show "$action" "${args[@]}";;esac
}
lat_ui_optional_input() {
 local value rc
 case $LAT_UI in
 dialog) value=$(dialog --stdout --inputbox "$1" 10 76);rc=$?;;
 whiptail) value=$(whiptail --inputbox "$1" 10 76 3>&1 1>&2 2>&3);rc=$?;;
 *)printf '%s: ' "$1" >&2;IFS= read -r value;rc=$?;;esac
 ((rc==0))||return 1;printf '%s' "$value"
}
lat_ui_secret() {
 local value rc
 case $LAT_UI in
 dialog) value=$(dialog --stdout --passwordbox "$1" 10 76);rc=$?;;
 whiptail) value=$(whiptail --passwordbox "$1" 10 76 3>&1 1>&2 2>&3);rc=$?;;
 *)[[ -t 0 ]]||return 1;IFS= read -r -s -p "$1: " value;rc=$?;printf '\n' >&2;;esac
 ((rc==0))||return 1;printf '%s' "$value"
}
lat_shared_processes() {
 local pid start signal
 lat_ui_show_text "$(ps -eo pid,ppid,user,pcpu,pmem,stat,args --sort=-pcpu | head -n 40)"
 pid=$(lat_ui_input PID)||return
 [[ $pid =~ ^[0-9]+$ && -r /proc/$pid/stat ]]||return
 start=$(aw_process_starttime "$pid")||return
 lat_ui_show_text "$(aw_process_details "$pid")"
 signal=$(lat_ui_menu Signal TERM SIGTERM KILL SIGKILL 0 "$(lat_t back)")||return
 [[ $signal == TERM || $signal == KILL ]]||return
 lat_ui_confirm "$signal -> PID $pid"||return
 lat_backend_show process.signal "$pid" "$start" "$signal"
}
lat_shared_main() {
 local page action tag text choice
 local pages=() actions=()
 while IFS=$'\t' read -r tag text;do pages+=("$tag" "$text");done < <(python3 -I "$LAT_ROOT/gui/catalog.py" pages "$LAT_LANGUAGE")
 while true;do
  page=$(lat_ui_menu 'Linux Adminw21 v1' "${pages[@]}" optional 'nload / iftop / nethogs' 0 "$(lat_t exit)")||return
  case $page in
  0)return;;dashboard)lat_ui_show_text "$(aw_metrics)";continue;;processes)lat_shared_processes;continue;;
  reports)lat_reports_menu;continue;;
  settings)choice=$(lat_ui_menu "$(lat_t settings)" language "$(lat_t change_language)" check "$(lat_t health)" 0 "$(lat_t back)")||continue
   case $choice in language)lat_settings;lat_shared_main;return;;check)lat_backend_show capabilities;;esac;continue;;
  optional)choice=$(lat_ui_menu 'Optional tools' nload nload iftop iftop nethogs nethogs 0 "$(lat_t back)")||continue
   case $choice in nload|iftop|nethogs)if command -v "$choice" >/dev/null;then "$choice";else lat_ui_notice "$(lat_t missing)";fi;;esac;continue;;esac
  actions=()
  while IFS=$'\t' read -r tag text;do actions+=("$tag" "$text");done < <(python3 -I "$LAT_ROOT/gui/catalog.py" actions "$LAT_LANGUAGE" "$page")
  action=$(lat_ui_menu "$page" "${actions[@]}" 0 "$(lat_t back)")||continue
  [[ $action == 0 ]]||lat_shared_action "$action"
 done
}
lat_reports_menu() {
 local out format
 format=$(lat_ui_menu Report txt TXT json JSON html HTML 0 "$(lat_t back)")||return
 [[ $format == txt || $format == json || $format == html ]]||return
 out=$(lat_ui_input 'New report path')||return
 [[ $out == *."$format" && ! -e $out ]]||return
 lat_ui_confirm "Save $out"||return
 local python=python3
 [[ ! -x $LAT_ROOT/venv/bin/python3 ]] || python="$LAT_ROOT/venv/bin/python3"
 "$python" "$LAT_ROOT/gui/report_cli.py" "$out"
 lat_ui_notice "Report exit: $?"
}
