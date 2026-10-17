#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state"
source "$ROOT/lib/common.sh"
source "$ROOT/lib/config.sh"
source "$ROOT/lib/i18n.sh"
source "$ROOT/lib/logging.sh"
source "$ROOT/lib/menu.sh"
source "$ROOT/modules/accounts.sh"
lat_config_init; lat_load_translations;lat_log_init
LAT_UI=plain
lat_ui_notice() { :; }
lat_valid_account 'testuser'
lat_valid_account 'a_1'
if lat_valid_account 'root;id';then exit 1;fi
if lat_valid_account '../etc';then exit 1;fi
if lat_valid_account 'name with space';then exit 1;fi
if lat_valid_group 'bad group';then exit 1;fi
lat_system_protected root
lat_system_protected nobody
lat_system_protected daemon
# Test no root action on cancellation or malformed input.
lat_ui_confirm() { return 1; }
lat_ui_input() { printf '%s\n' 'root;rm'; }
lat_input_account >/dev/null 2>&1 && exit 1
lat_ui_input() { printf '%s\n' 'testuser'; }
lat_account_exists() { return 1; }
lat_run_action() { echo UNSAFE_ACTION >> "$TMP/unsafe"; return 0; }
lat_ui_menu() { printf '%s\n' yes; }
lat_user_create
[[ ! -e $TMP/unsafe ]]
# Translation coverage for all new prompts.
for key in username_prompt group_prompt create_user delete_user change_password create_group delete_group add_to_group remove_from_group; do
 [[ $(LAT_LANGUAGE=de; lat_t "$key") != "$key" ]]
 [[ $(LAT_LANGUAGE=en; lat_t "$key") != "$key" ]]
done
printf 'PASS: v1 account validators, protected accounts, cancellation, translation coverage\n'
