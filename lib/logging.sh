#!/usr/bin/env bash
lat_log_init() {
 LAT_LOG_HOME="${XDG_STATE_HOME:-$HOME/.local/state}/adminw21"
 (umask 077; mkdir -p -- "$LAT_LOG_HOME") || return 1
 LAT_LOG_FILE="$LAT_LOG_HOME/operations.log"
 (umask 077; touch -- "$LAT_LOG_FILE") || return 1
 chmod 600 "$LAT_LOG_FILE" || return 1
}
# Only predefined event codes are logged; never store arguments or secrets.
lat_log() {
 local event=$1 status=$2
 case "$event" in START|EXIT|LANGUAGE_CHANGE|INFO_VIEW|HEALTH_VIEW|USERS_VIEW|SETTINGS_VIEW|ACCOUNT_CREATE|ACCOUNT_DELETE|PASSWORD_CHANGE|ACCOUNT_LOCK|ACCOUNT_UNLOCK|GROUP_CREATE|GROUP_DELETE|GROUP_ADD|GROUP_REMOVE|USERS_LIST|GROUPS_LIST|FILE|PACKAGE|SERVICE|PROCESS|BACKUP|CRON|REPORT) ;; *) return 1;; esac
 case "$status" in OK|FAILED) ;; *) return 1;; esac
 printf '%s\tevent=%s\tstatus=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$event" "$status" >> "$LAT_LOG_FILE"
}
