#!/usr/bin/env bash
# Translation files contain literal KEY=value lines, never executable shell.
declare -Ag LAT_DE LAT_EN
lat_load_translations() {
 local line key value file language
 for language in de en; do
   file="$LAT_ROOT/lang/$language.conf"
   [[ -r $file ]] || { lat_error "Translation missing: $file"; return 1; }
   while IFS= read -r line || [[ -n $line ]]; do
      [[ -z $line || $line == \#* ]] && continue
      [[ $line == *=* ]] || continue
      key=${line%%=*}; value=${line#*=}
      [[ $key =~ ^[a-z_][a-z0-9_]*$ ]] || continue
      if [[ $language = de ]]; then LAT_DE["$key"]=$value; else LAT_EN["$key"]=$value; fi
   done < "$file"
 done
}
lat_t() {
 local key=$1
 if [[ $LAT_LANGUAGE = en ]]; then printf '%s' "${LAT_EN[$key]:-${LAT_DE[$key]:-$key}}"
 else printf '%s' "${LAT_DE[$key]:-$key}"; fi
}
