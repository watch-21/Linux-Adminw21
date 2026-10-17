#!/usr/bin/env bash
# v1 user and group administration. Never log secrets or command arguments.
lat_valid_account() { [[ $1 =~ ^[a-z_][a-z0-9_-]{0,30}\$?$ ]]; }
lat_valid_group() { [[ $1 =~ ^[a-z_][a-z0-9_-]{0,30}\$?$ ]]; }
lat_account_exists() { getent passwd "$1" >/dev/null 2>&1; }
lat_group_exists() { getent group "$1" >/dev/null 2>&1; }
lat_privileged() {
 if lat_is_root; then LAT_PRIV=( );
 elif lat_command_exists sudo; then LAT_PRIV=(sudo);
 else lat_ui_notice "$(lat_t need_sudo)"; return 1; fi
 # Test sudo permissions now; no silent policy bypass.
 if ((${#LAT_PRIV[@]})); then sudo -v || return 1; fi
}
lat_run_action() {
 local event=$1; shift
 if "${LAT_PRIV[@]}" "$@"; then
   lat_log "$event" OK
   lat_ui_notice "$(lat_t operation_success)"
 else
   lat_log "$event" FAILED
   lat_ui_notice "$(lat_t operation_failed)"
   return 1
 fi
}
lat_input_account() {
 local name
 name=$(lat_ui_input "$(lat_t username_prompt)") || return 1
 if ! lat_valid_account "$name"; then lat_ui_notice "$(lat_t invalid_name)"; return 1; fi
 printf '%s\n' "$name"
}
lat_input_group() {
 local group
 group=$(lat_ui_input "$(lat_t group_prompt)") || return 1
 if ! lat_valid_group "$group"; then lat_ui_notice "$(lat_t invalid_name)"; return 1; fi
 printf '%s\n' "$group"
}
lat_system_protected() {
 local entry uid
 [[ $1 != root && $1 != nobody && $1 != _* ]] || return 0
 entry=$(getent passwd "$1") || return 0
 IFS=: read -r _ _ uid _ _ _ _ <<< "$entry"
 [[ $uid =~ ^[0-9]+$ ]] || return 0
 (( uid < 1000 ))
}
lat_user_create() {
 local name home shell option
 name=$(lat_input_account) || return
 if lat_account_exists "$name"; then lat_ui_notice "$(lat_t already_exists)"; return; fi
 option=$(lat_ui_menu "$(lat_t home_prompt)" yes "$(lat_t yes)" no "$(lat_t no)") || return
 case $option in yes) home=-m ;; no) home=-M ;; *) return ;; esac
 shell=$(lat_ui_menu "$(lat_t shell_prompt)" bash /bin/bash sh /bin/sh none /usr/sbin/nologin) || return
 case $shell in bash) shell=/bin/bash ;; sh) shell=/bin/sh ;; none) shell=/usr/sbin/nologin ;; *) return ;; esac
 [[ -x $shell || $shell == /usr/sbin/nologin ]] || { lat_ui_notice "$(lat_t missing_shell)"; return; }
 lat_ui_confirm "$(lat_t confirm_create): $name" || return
 lat_privileged || return
 lat_run_action ACCOUNT_CREATE useradd "$home" -s "$shell" -- "$name" || return
 if lat_ui_confirm "$(lat_t password_prompt)"; then
   lat_password_set_for "$name"
 fi
}
lat_password_set_for() {
 local name=$1 pass1 pass2 result=1
 lat_privileged || return 1
 # Masked input in EVERY interface, never call interactive passwd behind dialog.
 if [[ ${LAT_UI:-plain} == zenity ]]; then
   pass1=$(zenity --password --title="Linux Adminw21 - Password" --width=460) || return 1
   pass2=$(zenity --password --title="Linux Adminw21 - Confirm password" --width=460) || { unset pass1; return 1; }
 elif [[ ${LAT_UI:-plain} == dialog ]]; then
   pass1=$(dialog --stdout --insecure --title 'Linux Adminw21' --passwordbox 'New password' 10 70) || return 1
   pass2=$(dialog --stdout --insecure --title 'Linux Adminw21' --passwordbox 'Confirm password' 10 70) || { unset pass1; return 1; }
 elif [[ ${LAT_UI:-plain} == whiptail ]]; then
   pass1=$(whiptail --title 'Linux Adminw21' --passwordbox 'New password' 10 70 3>&1 1>&2 2>&3) || return 1
   pass2=$(whiptail --title 'Linux Adminw21' --passwordbox 'Confirm password' 10 70 3>&1 1>&2 2>&3) || { unset pass1; return 1; }
 else
   [[ -t 0 ]] || { lat_ui_notice 'Interactive terminal required'; return 1; }
   read -r -s -p 'New password: ' pass1 || return 1; printf '\n' >&2
   read -r -s -p 'Confirm password: ' pass2 || { unset pass1; return 1; }; printf '\n' >&2
 fi
 if [[ -z $pass1 || $pass1 != "$pass2" || $pass1 == *:* || $pass1 == *$'\n'* || $pass1 == *$'\r'* ]]; then
   unset pass1 pass2
   lat_log PASSWORD_CHANGE FAILED
   lat_ui_notice 'Password invalid or confirmation does not match'
   return 1
 fi
 # Password is passed only through a pipe to chpasswd, never in argv, logs or files.
 if printf '%s:%s\n' "$name" "$pass1" | "${LAT_PRIV[@]}" chpasswd; then result=0; fi
 unset pass1 pass2
 if (( result == 0 )); then lat_log PASSWORD_CHANGE OK;lat_ui_notice "$(lat_t operation_success)";return 0;fi
 lat_log PASSWORD_CHANGE FAILED;lat_ui_notice "$(lat_t operation_failed)";return 1
}

lat_user_delete() {
 local name option entry home
 name=$(lat_input_account) || return
 lat_account_exists "$name" || { lat_ui_notice "$(lat_t not_found)"; return; }
 if lat_system_protected "$name"; then lat_ui_notice "$(lat_t protected_account)"; return; fi
 entry=$(getent passwd "$name"); IFS=: read -r _ _ _ _ _ home _ <<< "$entry"
 option=$(lat_ui_menu "$(lat_t delete_home_prompt)" keep "$(lat_t keep_home)" remove "$(lat_t remove_home)") || return
 lat_ui_confirm "$(lat_t confirm_delete): $name (home: $home; $option)" || return
 lat_privileged || return
 if [[ $option == remove ]]; then
   [[ $home == /home/* && $home != /home/ && $home != /home ]] || { lat_ui_notice "$(lat_t unsafe_home)"; return; }
   lat_run_action ACCOUNT_DELETE userdel -r -- "$name"
 else lat_run_action ACCOUNT_DELETE userdel -- "$name"; fi
}
lat_user_lock_toggle() {
 local event=$1 name
 name=$(lat_input_account) || return
 lat_account_exists "$name" || { lat_ui_notice "$(lat_t not_found)"; return; }
 lat_system_protected "$name" && { lat_ui_notice "$(lat_t protected_account)"; return; }
 lat_ui_confirm "$(lat_t confirm_change): $name" || return
 lat_privileged || return
 case $event in lock) lat_run_action ACCOUNT_LOCK usermod -L -- "$name";; unlock) lat_run_action ACCOUNT_UNLOCK usermod -U -- "$name";; esac
}
lat_user_password() {
 local name
 name=$(lat_input_account) || return
 lat_account_exists "$name" || { lat_ui_notice "$(lat_t not_found)"; return; }
 if lat_system_protected "$name"; then lat_ui_notice "$(lat_t protected_account)"; return; fi
 lat_password_set_for "$name"
}
lat_user_details() {
 local name entry
 name=$(lat_input_account) || return
 entry=$(getent passwd "$name") || { lat_ui_notice "$(lat_t not_found)"; return; }
 lat_ui_show_text "$entry"$'\n'"$(id "$name" 2>&1)"
}
lat_user_list() { lat_ui_show_text "$(getent passwd | cut -d: -f1 | head -n 50)"; }
lat_group_create() {
 local group
 group=$(lat_input_group) || return
 lat_group_exists "$group" && { lat_ui_notice "$(lat_t already_exists)"; return; }
 lat_ui_confirm "$(lat_t confirm_create): $group" || return
 lat_privileged || return
 lat_run_action GROUP_CREATE groupadd -- "$group"
}
lat_group_delete() {
 local group gid entry
 group=$(lat_input_group) || return
 entry=$(getent group "$group") || { lat_ui_notice "$(lat_t not_found)"; return; }
 IFS=: read -r _ _ gid _ <<< "$entry"
 [[ $gid =~ ^[0-9]+$ ]] || return
 if (( gid < 1000 )) || [[ $group == sudo || $group == wheel || $group == root ]]; then
   lat_ui_notice "$(lat_t protected_account)"; return
 fi
 lat_ui_confirm "$(lat_t confirm_delete): $group" || return
 lat_privileged || return
 lat_run_action GROUP_DELETE groupdel -- "$group"
}
lat_group_membership() {
 local op=$1 name group
 name=$(lat_input_account) || return
 lat_account_exists "$name" || { lat_ui_notice "$(lat_t not_found)"; return; }
 lat_system_protected "$name" && { lat_ui_notice "$(lat_t protected_account)"; return; }
 group=$(lat_input_group) || return
 lat_group_exists "$group" || { lat_ui_notice "$(lat_t not_found)"; return; }
 # Refuse to silently change an account's primary group.
 if [[ $(id -gn "$name") == "$group" ]]; then lat_ui_notice "$(lat_t primary_group)"; return; fi
 if [[ $group == sudo || $group == wheel ]]; then
    lat_ui_confirm "$(lat_t elevated_group): $name -> $group" || return
 fi
 lat_ui_confirm "$(lat_t confirm_change): $name -> $group" || return
 lat_privileged || return
 if [[ $op == add ]]; then
   lat_run_action GROUP_ADD usermod -aG "$group" -- "$name"
 else
   if lat_command_exists gpasswd; then
     lat_run_action GROUP_REMOVE gpasswd -d "$name" "$group"
   else
     lat_ui_notice "$(lat_t missing_gpasswd)"
   fi
 fi
}
lat_group_list() { lat_ui_show_text "$(getent group | cut -d: -f1 | head -n 50)"; }
lat_group_details() {
 local group
 group=$(lat_input_group) || return
 lat_ui_show_text "$(getent group "$group" || printf '%s' "$(lat_t not_found)")"
}
lat_users_menu() {
 local choice
 while true; do
 choice=$(lat_ui_menu "$(lat_t menu_02)" 1 "$(lat_t create_user)" 2 "$(lat_t delete_user)" 3 "$(lat_t change_password)" 4 "$(lat_t lock_user)" 5 "$(lat_t unlock_user)" 6 "$(lat_t user_details)" 7 "$(lat_t list_users)" 0 "$(lat_t back)") || return
 case $choice in 1) lat_user_create;; 2) lat_user_delete;; 3) lat_user_password;;4) lat_user_lock_toggle lock;;5) lat_user_lock_toggle unlock;;6) lat_user_details;;7) lat_user_list;;0) return;;*)lat_ui_notice "$(lat_t invalid_option)";;esac
 done
}
lat_groups_menu() {
 local choice
 while true; do
 choice=$(lat_ui_menu "$(lat_t menu_03)" 1 "$(lat_t create_group)" 2 "$(lat_t delete_group)" 3 "$(lat_t add_to_group)" 4 "$(lat_t remove_from_group)" 5 "$(lat_t group_details)" 6 "$(lat_t list_groups)" 0 "$(lat_t back)") || return
 case $choice in 1) lat_group_create;;2) lat_group_delete;;3) lat_group_membership add;;4) lat_group_membership remove;;5) lat_group_details;;6) lat_group_list;;0) return;;*)lat_ui_notice "$(lat_t invalid_option)";;esac
 done
}
