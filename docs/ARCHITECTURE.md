# Linux Adminw21 v1 architecture

## Components

`admin.sh` selects the native Qt or terminal interface. `lib/menu.sh` provides dialog/whiptail/plain widgets; `lib/bridge.sh` and `gui/catalog.py` share action metadata with the GUI. Bash libraries, distribution detection, translations and administration modules provide native operations.

`gui/dashboard.py` owns the dashboard layout; `gui/widgets.py` paints icons/charts and supplies table items. `gui/controls.py` supplies clickable/keyboard metric cards, range segments and responsive action shelves. Available screen geometry bounds startup; metrics use 4/2/1 columns, panels stack below 960 px, and action forms scroll. Hover reads the nearest stored measurement.

## Execution and privileges

- The GUI runs as the desktop user. Qt launches argument-vector `QProcess` jobs. Foreground request generations prevent stale results from replacing newer output; quiet reads preserve action output. Read jobs have bounded timeouts and can be cancelled; privileged writes finish normally.
- Root operations use `/usr/bin/pkexec /usr/local/share/adminw21/backend/backend.sh ACTION ARG...`. The policy requires active-session administrator authorization without retained authorization caching. No background administration service or arbitrary command endpoint is created.
- Before sourcing privileged code, the backend checks the fixed install path, caller and root-owned/non-writable/non-symlink backend/library/module trees. It repeats privilege/caller checks before dispatch, fixes PATH/Python import mode and clears command-specific option variables.
- `modules/backend_actions.sh` validates operation-specific inputs and invokes native utilities using quoted arguments/arrays. Passwords are newline-free stdin data followed by EOF, processed through `chpasswd`; embedded NUL is rejected. Fields and mutable transfer buffers are cleared. Immutable Python/Qt objects cannot guarantee forensic memory erasure.
- Root file changes require trusted parent trees. SSH key writes run as the target account. `backend/protocol.py` supplies JSON serialization, numeric Cron validation and passive archive validation.

## Backend contract

Command: `backend/backend.sh ACTION ARG...`. The finite router accepts known actions and validated arguments. Recognized actions return one JSON object:

```json
{"schema":1,"version":"v1","action":"users.list","ok":true,"status":0,"timestamp":"UTC ISO8601","output":"native output"}
```

Output reaches the serializer through stdin. Process exit status matches `status`: 2 rejected input, 10 partial account creation/inspection, 69 unavailable capability, 77 missing authorization. Native failures retain a nonzero status; reports retain failed checks.

## Monitoring and sessions

A dedicated `QThread` samples psutil/native Linux sources every two seconds. Monitoring performs no administrative mutations. CPU guest counters are not double counted; first-sample rates are unavailable. Address/state sources fail independently from counters. Services use the Bash backend at most once per 30 seconds; session discovery refreshes at most every 10 seconds with bounded subprocess timeouts.

History contains at most 2700 compact CPU/RAM/network/disk records, covering 90 minutes. CPU/RAM plots use a 100% scale; I/O graphs adapt. Network rates use MiB/s. Process CPU can exceed 100% on multicore systems. Failed current-state collection clears stale displays.

`backend/sessions.py` prefers logind, excludes greeter/manager/background/closing sessions and falls back to utmp. It reports source availability/limitations, NSS groups and effective process groups when visible. Distinct users and sessions are counted separately. No login is inferred from the GUI process's own account.

## Installation and data

`lib/install_paths.sh` supplies installer/uninstaller path guards. Staging and registration snapshots precede switching; failures restore the previous application and registrations. Unknown registrations are rejected. `--destdir` stages packaging files without changing privileged runtime paths or registering on the running host.

| Data | Location |
|---|---|
| GUI preferences | `$XDG_CONFIG_HOME/adminw21/gui.json` |
| Terminal preferences | `$XDG_CONFIG_HOME/adminw21/settings.conf` |
| Privileged audit | `/var/log/adminw21/operations.log` |
| Captures | `/var/lib/adminw21/captures` |
| Backup jobs | `/etc/adminw21/jobs` |
| Owned schedules | `/etc/cron.d/adminw21-*` |
| Backup/installation archives | `/var/backups/adminw21` |

Settings are data, not sourced shell. Audit records contain action/status/caller, not passwords. Capture directories/files use modes 700/600. No startup service is registered. Updates and uninstall preserve settings, logs and data.

## Limits

Process signalling revalidates start ticks but does not use pidfds; a narrow check/signal race remains. Root filesystem mutations refuse user-writable directory trees. Restore requires an empty protected destination and rejects linked/special entries, archives over 20 GiB or over 100,000 entries. Native desktop authorization and distribution-specific mutations require further verification as described in [TEST_REPORT.md](TEST_REPORT.md).
