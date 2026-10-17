#!/usr/bin/env bash
set -o pipefail
LAT_START_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$LAT_START_DIR/lib/common.sh"
source "$LAT_ROOT/lib/config.sh"
source "$LAT_ROOT/lib/i18n.sh"
source "$LAT_ROOT/lib/distro.sh"
source "$LAT_ROOT/lib/logging.sh"
source "$LAT_ROOT/lib/menu.sh"
source "$LAT_ROOT/modules/accounts.sh"
source "$LAT_ROOT/modules/operations.sh"
source "$LAT_ROOT/modules/performance.sh"
if [[ $# == 0 && $EUID != 0 && -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]];then set -- --gui;fi
# GUI runs as the desktop user. Root authentication is action-specific.
case "${1:-}" in
 --gui) shift
  if ((EUID==0));then echo 'Use adminw21 --gui as the desktop user' >&2;exit 77;fi
  if [[ -z ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]];then echo 'No desktop display. Use sudo adminw21 --terminal.' >&2;exit 69;fi
  PYTHON="$LAT_ROOT/venv/bin/python3"
  [[ -x $PYTHON ]]||PYTHON=python3
  if ! "$PYTHON" -I "$LAT_ROOT/gui/runtime_check.py";then
   echo 'GUI dependencies missing or incompatible. Run sudo ./install.sh, or use sudo adminw21 --terminal.' >&2;exit 69
  fi
  exec "$PYTHON" "$LAT_ROOT/gui/app.py" "$@";;
 --backend) shift;exec "$LAT_ROOT/backend/backend.sh" "$@";;
 --help|-h) printf 'Linux Adminw21 v1\nadminw21 --gui\nsudo adminw21 --terminal\nadminw21 --diagnose|--version|--health|--users\n';exit 0;;
 --version) echo v1;exit 0;;
esac
if [[ ${1:-} == --terminal || ${1:-} == --tui || -z ${1:-} ]];then
 ((EUID==0))||{ echo 'Use sudo adminw21 --terminal' >&2;exit 77; }
fi
LAT_REQUESTED_UI=auto
case "${1:-}" in
 --gui) LAT_REQUESTED_UI=gui; shift ;;
 --terminal|--tui) LAT_REQUESTED_UI=terminal; shift ;;
esac
lat_config_init
lat_load_translations || exit 1
lat_detect_distro
lat_ui_detect
lat_diagnose() {
 printf 'Linux Adminw21 %s\n' "$LAT_VERSION"
 printf 'UID=%s EUID=%s USER=%s HOME=%s\n' "$(id -u)" "$EUID" "${USER:-unknown}" "$HOME"
 printf 'Mode requested: %s; detected: %s\n' "$LAT_REQUESTED_UI" "$LAT_UI"
 printf 'DISPLAY=%s WAYLAND_DISPLAY=%s XDG_SESSION_TYPE=%s\n' "${DISPLAY:-<unset>}" "${WAYLAND_DISPLAY:-<unset>}" "${XDG_SESSION_TYPE:-<unset>}"
 for program in bash python3 dialog whiptail pkexec sudo git; do
  if lat_command_exists "$program"; then printf '%s: found\n' "$program"; else printf '%s: missing\n' "$program"; fi
 done
 if [[ $LAT_REQUESTED_UI == gui ]]; then
  if [[ -z ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]]; then
   printf 'GUI unavailable: no display environment. Open a desktop session or use --terminal.\n'
  elif ! lat_command_exists zenity; then
   printf 'GUI unavailable: install zenity through your distribution package manager.\n'
  else
   printf 'GUI display detected but accessibility is not guaranteed under sudo/root (especially Wayland).\n'
  fi
 fi
 printf 'Active installed binary: %s\n' "$(command -v adminw21 || echo not-in-PATH)"
 printf 'Legacy binary: %s\n' "$(command -v linux-admin || echo not-in-PATH)"
}
if [[ $LAT_REQUESTED_UI == gui && $LAT_UI != zenity && ${1:-} != --diagnose ]]; then
 lat_diagnose >&2
 lat_error 'Cannot launch graphical mode. See diagnosis above. Use sudo adminw21 --terminal.'
 exit 69
fi
if [[ $LAT_REQUESTED_UI == terminal && $LAT_UI == zenity ]]; then
 LAT_UI=plain
 if [[ -t 0 && -t 1 ]]; then
  if lat_command_exists dialog; then LAT_UI=dialog
  elif lat_command_exists whiptail; then LAT_UI=whiptail; fi
 fi
fi
lat_config_prepare || { lat_error 'Cannot create configuration'; exit 1; }
lat_log_init || { lat_error 'Cannot create log'; exit 1; }
source "$LAT_ROOT/lib/bridge.sh"
lat_log START OK
lat_health() {
 local dependency results=""
 for dependency in bash git dialog whiptail sudo; do
  if lat_command_exists "$dependency"; then results+="$dependency: $(lat_t available)"$'\n'; else results+="$dependency: $(lat_t missing)"$'\n';fi
 done
 results+="$(lat_t distribution): $LAT_DISTRO"$'\n'"$(lat_t package_manager): $LAT_PKGMGR"$'\n'"$(lat_t compatibility): $(lat_t compatibility_note)"
 printf '%s\n' "$results"
}
lat_users() {
 # Read-only inspection, not account management.
 getent passwd | cut -d: -f1 | head -n 30
}
lat_settings() {
 local answer
 while true; do
  answer=$(lat_ui_menu "$(lat_t settings)" 1 "$(lat_t change_language)" 0 "$(lat_t back)") || return
  case "$answer" in
   1) answer=$(lat_ui_menu "$(lat_t change_language)" de 'Deutsch' en 'English' 0 "$(lat_t back)") || continue
      case "$answer" in de|en) if lat_config_language "$answer"; then lat_log LANGUAGE_CHANGE OK;lat_ui_notice "$(lat_t language_saved)";else lat_log LANGUAGE_CHANGE FAILED;fi;; esac;;
   0) return;; *) lat_ui_notice "$(lat_t invalid_option)";;
  esac
 done
}
lat_main() {
 local answer labels=() index label
 while true; do
  labels=()
  for index in {1..15}; do printf -v label 'menu_%02d' "$index"; labels+=("$index" "$(lat_t "$label")");done
  labels+=(0 "$(lat_t exit)")
  answer=$(lat_ui_menu "$(lat_t app_title) $LAT_VERSION" "${labels[@]}") || break
  case "$answer" in
   15) lat_log SETTINGS_VIEW OK;lat_settings;;
   1) lat_log INFO_VIEW OK;aw_dashboard;;
   2) lat_users_menu;;
   3) lat_groups_menu;;
   0) break;;
   4|5|6|7|8|9|10|11|12|13|14) aw_module "$answer";;
   *) lat_ui_notice "$(lat_t invalid_option)";;
  esac
 done
}
case "${1:-}" in
 --diagnose) lat_diagnose;;
 --help|-h) printf 'Linux Adminw21 %s\nUsage: %s [--gui|--terminal] [--diagnose|--help|--version|--health|--users]\n' "$LAT_VERSION" "$0";;
 --version) printf '%s\n' "$LAT_VERSION";;
 --health) lat_log HEALTH_VIEW OK;lat_health;;
 --users) lat_log USERS_VIEW OK;lat_users;;
 '') if [[ $LAT_UI != zenity && ( ! -t 0 || ! -t 1 ) ]];then lat_error 'A terminal is required. Use --gui for desktop mode.';exit 2;fi;lat_shared_main;;
 *) lat_error 'Unknown option. Use --help.';exit 2;;
esac
lat_log EXIT OK
