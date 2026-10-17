# Feature scope — Linux Adminw21 v1

| Area | Implemented behavior | Limits |
|---|---|---|
| Desktop | Native Qt dashboard, live cards/charts, range controls, keyboard navigation, page search, responsive action tiles, DE/EN, light/dark | Real desktop display and PolicyKit agent verification remain open |
| Sessions | logind discovery with utmp fallback, distinct users/sessions, current NSS groups, remote source and duration, session details | utmp can omit graphical/Wayland logins; configured groups can differ from a running session's effective groups |
| Monitoring | Total/per-core CPU, RAM/Swap, root/mounted filesystem usage/inodes, network/disk rates, bounded history | First rates need two samples; topology, interfaces and permissions depend on the host |
| Processes | Search/filter, numeric sorting, stable selection, details, confirmed TERM/KILL and start-tick revalidation | Essential processes are protected; no pidfd, so a narrow check/signal race remains |
| Accounts/groups | Create/password/lock/unlock/delete/details, home/shell/groups/sudo, additive membership, validated SSH keys | Partial account creation is reported; arbitrary home destinations are unavailable; some native mutations still require VM validation |
| Packages | APT, DNF/YUM, Pacman, Zypper, APK, XBPS and Portage adapters | Write operations require distribution-specific VM validation; NixOS/OSTree mutation and release upgrades are unavailable |
| Services | systemd listing/logs/start/stop/restart/enable/disable with essential service protection | Real systemd operations require VM validation; OpenRC/runit mutation is unavailable |
| Network | Counters/rates, addresses/routes/DNS/sockets/ping; bounded capture with caller/identity-checked stop | Capture and live authorization require VM validation; fixed protected output directory, no GUI per-process traffic analyzer |
| Backups | Create, validation, empty-target restore, generated-name retention and fixed scheduling | Archive links/special files rejected; scheduled execution requires daemon validation |
| Cron | Revision-checked add/edit/toggle/delete of owned jobs; unrelated entries preserved | Numeric schedules and two fixed commands; no advanced expressions or next-run calendar |
| Files | Listing/find/text search/size; individual mkdir/touch/chmod/chown/copy/move/delete | Root writes in user-controlled trees refused; no recursive permission preview or full icon explorer |
| Security | SSH configuration, firewall/port/login/group/service inspection; tagged UFW allow rules | Native firewall mutations require VM validation; no general SSH/firewall policy editor or classified CVE feed |
| Reports | Timestamped TXT/JSON/HTML exports with failures and source limits; private non-overwriting files | Explicit collection required; some sources need administrative read permissions |
| Terminal | dialog/whiptail/numbered menus, DE/EN, shared action catalog/backend | Interactive dialog/whiptail behavior requires terminal verification |
| Installation | Runtime preflight, private venv repair, transactional staging/rollback, owned-file guards, terminal-only registration cleanup | Actual desktop activation/authentication requires verification; unknown legacy launchers remain for manual review |

Local regression results and verification boundaries are in [TEST_REPORT.md](TEST_REPORT.md). Available adapters and test targets do not imply certification of every supported distribution.
