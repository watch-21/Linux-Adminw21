#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
export HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state"
mkdir -p "$HOME"
for file in "$ROOT"/*.sh "$ROOT"/lib/*.sh "$ROOT"/modules/*.sh; do bash -n "$file";done
[[ $("$ROOT/admin.sh" --version) == v1 ]]
"$ROOT/admin.sh" --health | grep -q 'Distribution:'
"$ROOT/admin.sh" --help | grep -q -- '--users'
"$ROOT/admin.sh" --users >/dev/null
"$ROOT/admin.sh" --bogus >/dev/null 2>&1 && { echo 'Failed unknown-option test' >&2;exit 1; }
# shellcheck source=../lib/common.sh
source "$ROOT/lib/common.sh"
source "$ROOT/lib/config.sh"
source "$ROOT/lib/i18n.sh"
lat_config_init;lat_load_translations
lat_validate_name 'max_5'
if lat_validate_name '../bad';then exit 1;fi
if lat_validate_name 'bad;command';then exit 1;fi
lat_validate_path '/home/example'
if lat_validate_path 'relative/path';then exit 1;fi
lat_config_prepare
lat_config_language en
lat_config_init
[[ $LAT_LANGUAGE = en ]]
[[ $(lat_t press_enter) == 'Press Enter to continue ...' ]]
lat_config_language de
[[ $(lat_t press_enter) == 'Weiter mit Enter ...' ]]
# Config text is data, not shell code.
# shellcheck disable=SC2016 # Test that literal shell expressions are not evaluated.
printf 'LANGUAGE=en\nDANGER=$(touch %s/pwned)\n' "$TMP" > "$LAT_CONFIG"
lat_config_init
[[ ! -e "$TMP/pwned" ]]
[[ $LAT_LANGUAGE = en ]]
[[ $(stat -c %a "$LAT_CONFIG") == 600 ]]
echo 'PASS: syntax, CLI, language, config, validation, and read-only commands'
