#!/bin/bash
# Fixed action router; never source configuration or evaluate caller strings.
set -o pipefail
set +x
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
unset BASH_ENV ENV PYTHONPATH PYTHONHOME CDPATH
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
export PYTHONSAFEPATH=1
# Reject elevated untrusted trees before loading any code.
if [[ -n ${PKEXEC_UID:-} ]];then
 [[ $ROOT == /usr/local/share/adminw21 && $PKEXEC_UID =~ ^[0-9]+$ ]] || exit 77
 for component in /usr /usr/local /usr/local/share "$ROOT";do
  [[ ! -L $component && $(stat -c %u "$component") == 0 ]] || exit 77
  mode=$(stat -c %a "$component")
  [[ ! $mode =~ [2367][0-9]$ && ! $mode =~ [2367]$ ]] || exit 77
 done
 [[ -z $(find "$ROOT/backend" "$ROOT/lib" "$ROOT/modules" \( ! -user root -o -perm /022 -o -type l \) -print -quit) ]] || exit 77
fi
# Reset command-specific option environments as well as executable lookup.
unset TAR_OPTIONS APT_CONFIG PERL5OPT PERL5LIB RUBYOPT SYSTEMD_EDITOR SYSTEMD_PAGER SYSTEMD_PAGERSECURE
source "$ROOT/lib/common.sh"
source "$ROOT/lib/distro.sh"
source "$ROOT/modules/backend_actions.sh"
AW_ACTION=${1:-}; shift || :
aw_response() { printf '%s' "$2" | /usr/bin/python3 -I "$ROOT/backend/protocol.py" response "$AW_ACTION" "$1"; }
aw_fail() { printf '%s\n' "$1" >&2; return "${2:-2}"; }
# Fixed read-only actions may be used without authentication.
case "$AW_ACTION" in
 capabilities|sessions.list|users.list|users.info|groups.list|groups.info|services.list|services.logs|packages.search|packages.list|packages.details|packages.updates|network.info|network.ping|storage.info|files.list|files.find|files.search|files.size|backup.list|backup.verify|backup.preview|cron.list|logs.search|security.inspect) privileged=no ;;
 user.create|user.password|user.delete|user.lock|user.unlock|user.shell|user.primary|user.home|user.ssh.add|user.ssh.remove|group.create|group.delete|group.add|group.remove|process.signal|service.start|service.stop|service.restart|service.enable|service.disable|package.install|package.remove|package.refresh|package.upgrade|package.clean|package.autoremove|file.mkdir|file.touch|file.chmod|file.chown|file.copy|file.move|file.delete|backup.create|backup.restore|backup.retention|backup.schedule|backup.run|backup.schedule.remove|cron.add|cron.edit|cron.toggle|cron.delete|capture.start|capture.stop|firewall.add|firewall.remove) privileged=yes ;;
 *) aw_response 2 'Unknown or disallowed action'; exit 2 ;;
esac
# Enforce exact action arity before any operation.
case "$AW_ACTION" in
 capabilities|sessions.list|users.list|groups.list|services.list|packages.list|packages.updates|network.info|storage.info|security.inspect|package.refresh|package.upgrade|package.clean|package.autoremove|capture.stop) expected=0;;
 user.create) expected=6;;process.signal|cron.add|cron.edit|cron.toggle|cron.delete|backup.schedule) expected=3;;capture.start) expected=4;;
 users.info|groups.info|user.password|user.lock|user.unlock|group.create|group.delete|services.logs|service.*|packages.search|packages.details|package.install|package.remove|network.ping|files.list|files.size|file.mkdir|file.touch|file.delete|backup.list|backup.verify|backup.preview|backup.run|backup.schedule.remove|cron.list) expected=1;;
 *) expected=2;;
esac
if [[ $AW_ACTION == logs.search ]];then
 (( $# <= 2 )) || { aw_response 2 'Wrong argument count';exit 2; }
else
 (( $# == expected )) || { aw_response 2 'Wrong argument count';exit 2; }
fi
if [[ $privileged == yes ]]; then
 if ((EUID != 0)); then aw_response 77 'Root authentication required';exit 77;fi
 if [[ -n ${PKEXEC_UID:-} ]]; then
  if ! [[ $PKEXEC_UID =~ ^[0-9]+$ ]] || ! getent passwd "$PKEXEC_UID" >/dev/null;then aw_response 77 'Invalid caller';exit 77;fi
  # An elevated caller may only use a system-installed, root-owned code tree.
  [[ $ROOT == /usr/local/share/adminw21 ]] || { aw_response 77 'Install backend before PolicyKit use';exit 77; }
  if find "$ROOT/backend" "$ROOT/lib" "$ROOT/modules" \( ! -user root -o -perm /022 -o -type l \) -print -quit | /usr/bin/grep -q .;then
   aw_response 77 'Unsafe backend ownership/permissions';exit 77
  fi
 fi
 umask 077
fi
# Output is captured in memory; password input is never reflected in diagnostics.
output=$(aw_dispatch "$AW_ACTION" "$@" 2>&1);rc=$?
[[ -n $output ]] || { if ((rc==0));then output="Operation completed";else output="Operation failed (status $rc); invalid input, missing capability or system command failure";fi; }
# Only action code and result enter the audit log.
if [[ $privileged == yes && $ROOT == /usr/local/share/adminw21 ]]; then
 if [[ ! -L /var/log/adminw21 ]];then
  install -d -m 700 -o root -g root /var/log/adminw21
  if [[ ! -L /var/log/adminw21/operations.log && ( ! -e /var/log/adminw21/operations.log || $(stat -c %h /var/log/adminw21/operations.log) == 1 ) ]];then
   printf '%s action=%s status=%s caller=%s\n' "$(date -u +%FT%TZ)" "$AW_ACTION" "$rc" "${PKEXEC_UID:-0}" >> /var/log/adminw21/operations.log
  fi
 fi
fi
aw_response "$rc" "$output"
exit "$rc"
