#!/usr/bin/env bash
lat_config_init() {
 LAT_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/adminw21"
 LAT_CONFIG="$LAT_CONFIG_HOME/settings.conf"
 LAT_LANGUAGE=de
 # Read exactly the expected value; do not execute configuration as shell code.
 if [[ -f $LAT_CONFIG ]]; then
   local line
   while IFS= read -r line || [[ -n $line ]]; do
      case "$line" in LANGUAGE=de) LAT_LANGUAGE=de;; LANGUAGE=en) LAT_LANGUAGE=en;; esac
   done < "$LAT_CONFIG"
 fi
}
lat_config_language() {
 [[ $1 == de || $1 == en ]] || return 1
 local previous
 previous=$(umask 077; mktemp "$LAT_CONFIG_HOME/.settings.XXXXXXXX") || return 1
 printf 'LANGUAGE=%s\n' "$1" > "$previous" || { rm -f -- "$previous"; return 1; }
 chmod 600 "$previous" || { rm -f -- "$previous"; return 1; }
 mv -f -- "$previous" "$LAT_CONFIG" || return 1
 LAT_LANGUAGE=$1
}
lat_config_prepare() {
 (umask 077; mkdir -p -- "$LAT_CONFIG_HOME") || return 1
 [[ -f $LAT_CONFIG ]] || lat_config_language "$LAT_LANGUAGE"
}
