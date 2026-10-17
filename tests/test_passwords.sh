#!/bin/bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
source "$ROOT/lib/common.sh"
source "$ROOT/modules/backend_actions.sh"
# These functions replace system mutations. No real accounts are modified.
aw_name() { [[ $1 == disposable ]]; }
aw_shell() { [[ $1 == /bin/bash ]]; }
getent() { return 1; }
useradd() { [[ $* == '-M -s /bin/bash -- disposable' ]]; }
chpasswd() {
 local line
 IFS= read -r line
 [[ $line == 'disposable:Test:colon password' ]]
}
printf '%s\n' 'Test:colon password' | aw_dispatch user.create disposable no /bin/bash '' '' no >/dev/null
chpasswd() { return 1; }
set +e
output=$(printf '%s\n' 'not-printed-secret' | aw_dispatch user.create disposable no /bin/bash '' '' no);rc=$?
set -e
[[ $rc == 10 && $output == *PARTIAL* && $output != *not-printed-secret* ]]
if printf 'first\nsecond\n' | aw_dispatch user.create disposable no /bin/bash '' '' no >/dev/null;then exit 1;fi
printf 'PASS: mocked password stdin, colon handling, partial creation and multiline rejection\n'
source "$ROOT/lib/i18n.sh"
source "$ROOT/lib/menu.sh"
LAT_LANGUAGE=en
lat_load_translations
LAT_UI=plain
selection=$(printf '2\n' | lat_ui_menu 'Fixture' first 'First' second 'Second' 0 'Back')
[[ $selection == second ]]
printf 'PASS: numbered terminal fallback maps choices to fixed action tags\n'
# NULs must be rejected, not silently removed by Bash read.
if printf 'first\0changed\n' | aw_dispatch user.create disposable no /bin/bash '' '' no >/dev/null;then exit 1;fi
printf 'PASS: embedded NUL password rejected before account creation\n'
