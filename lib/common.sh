#!/usr/bin/env bash
# Common helpers for Linux Adminw21
# shellcheck disable=SC2034 # Shared globals consumed by the entrypoint and modules.
LAT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
LAT_VERSION=v1
lat_error() { printf '%s\n' "ERROR: $*" >&2; }
lat_command_exists() { command -v "$1" >/dev/null 2>&1; }
lat_is_root() { [[ ${EUID:-$(id -u)} -eq 0 ]]; }
lat_need_root() { if ! lat_is_root; then lat_error "$(lat_t root_required)"; return 1; fi; }
lat_validate_name() { [[ $1 =~ ^[a-z_][a-z0-9_-]{0,31}\$?$ ]]; }
lat_validate_group() { lat_validate_name "$1"; }
lat_validate_path() { [[ -n $1 && $1 = /* && $1 != *$'\n'* && $1 != *$'\r'* ]]; }
lat_safe_confirm() { local answer; printf '%s [y/N]: ' "$1"; IFS= read -r answer || return 1; [[ $answer = y || $answer = Y || $answer = j || $answer = J ]]; }
lat_pause() { printf '\n%s ' "$(lat_t press_enter)"; IFS= read -r _ || :; }
lat_system_info() {
 printf '%s: %s\n' "$(lat_t hostname)" "$(hostname 2>/dev/null || echo unknown)"
 printf '%s: %s\n' "$(lat_t distribution)" "${LAT_DISTRO:-unknown}"
 printf '%s: %s\n' "$(lat_t package_manager)" "${LAT_PKGMGR:-unknown}"
 printf '%s: %s\n' "$(lat_t user)" "$(id -un)"
 printf '%s: %s\n' "$(lat_t privilege)" "$(lat_is_root && echo root || echo user)"
}
