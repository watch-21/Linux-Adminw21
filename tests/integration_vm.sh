#!/bin/bash
# Explicit opt-in: this suite mutates ONLY disposable fixtures in a throwaway VM.
set -euo pipefail
if [[ $EUID != 0 ]];then exit 77;fi
case ${1:-} in
 --disposable-vm) [[ ${ADMINW21_DISPOSABLE_VM:-} == yes ]] || exit 77;;
 --disposable-container)
  [[ ${ADMINW21_DISPOSABLE_CONTAINER:-} == yes && ( -f /.dockerenv || -f /run/.containerenv ) ]] || exit 77;;
 *)echo 'Use only in a throwaway VM/container with the explicit disposable flag';exit 77;;
esac
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
B="$ROOT/backend/backend.sh"
user=aw21test$$;group=aw21group$$
tmp=$(mktemp -d)
service=adminw21-test-$$.service
cleanup() {
 if getent passwd "$user" >/dev/null;then userdel -r -- "$user" 2>/dev/null||:;fi
 if getent group "$group" >/dev/null;then groupdel -- "$group"||:;fi
 if [[ -f /run/systemd/system/$service ]];then systemctl stop "$service"||:;rm -f "/run/systemd/system/$service";systemctl daemon-reload||:;fi
 # Fixture files are preserved for inspection after a failure.
 echo "Fixture directory: $tmp"
}
trap cleanup EXIT
password=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')
"$B" group.create "$group"
printf '%s\n' "$password" | "$B" user.create "$user" yes /bin/bash '' '' no
unset password
[[ $(passwd -S "$user" | awk '{print $2}') == P ]]
"$B" user.lock "$user"
[[ $(passwd -S "$user" | awk '{print $2}') == L ]]
"$B" user.unlock "$user"
[[ $(passwd -S "$user" | awk '{print $2}') == P ]]
"$B" group.add "$user" "$group"
id -nG "$user"|tr ' ' '\n'|grep -Fxq "$group"
"$B" group.remove "$user" "$group"
if id -nG "$user"|tr ' ' '\n'|grep -Fxq "$group";then exit 1;fi
if command -v crontab >/dev/null;then
 printf '* * * * * /usr/bin/true # unrelated-fixture\n'|crontab -u "$user" -
 revision=$(crontab -u "$user" -l | sha256sum|cut -d' ' -f1)
 "$B" cron.add "$user" "$revision" '0 * * * *|/usr/bin/true'
 revision=$(crontab -u "$user" -l|sha256sum|cut -d' ' -f1)
 "$B" cron.delete "$user" "$revision" 2
 crontab -u "$user" -l|grep -Fxq '* * * * * /usr/bin/true # unrelated-fixture'
else echo 'SKIP: crontab missing';fi
if [[ -d /run/systemd/system ]];then
 printf '[Unit]\nDescription=Adminw21 disposable test\n[Service]\nExecStart=/bin/sleep 60\n' >"/run/systemd/system/$service"
 systemctl daemon-reload
 "$B" service.start "$service"
 systemctl is-active "$service"
 "$B" service.stop "$service"
else echo 'SKIP: systemd not running';fi
mkdir "$tmp/source" "$tmp/restore"
printf 'backup fixture\n' >"$tmp/source/data"
"$B" backup.create "$tmp/source" "$tmp/backup.tar.gz"
"$B" backup.restore "$tmp/backup.tar.gz" "$tmp/restore"
python3 - "$tmp/source/data" "$tmp/restore/source/data" <<'PY'
import pathlib, sys
assert pathlib.Path(sys.argv[1]).read_bytes() == pathlib.Path(sys.argv[2]).read_bytes()
PY
"$B" packages.list >"$tmp/packages.json"
python3 - "$tmp/packages.json" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    result = json.load(stream)
assert result["ok"] and result["output"].strip(), result
print("PASS: native package inventory")
PY
"$B" user.delete "$user" remove
"$B" group.delete "$group"
echo 'PASS: disposable VM integration fixtures'
