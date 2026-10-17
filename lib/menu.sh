#!/usr/bin/env bash
lat_ui_detect() {
 LAT_UI=plain
 if [[ -t 0 && -t 1 ]];then
  if lat_command_exists dialog;then LAT_UI=dialog
  elif lat_command_exists whiptail;then LAT_UI=whiptail;fi
 fi
}
lat_ui_menu() {
 local title=$1;shift
 local result='' status
 case "$LAT_UI" in
 zenity)
  local args=()
  while (( $# >= 2 )); do args+=("$1" "$2");shift 2;done
  result=$(zenity --list --title="$title" --text="$(lat_t choose_option)" --column='#' --column="Option" --width=740 --height=570 "${args[@]}");status=$? ;;
 dialog) result=$(dialog --stdout --clear --title "$title" --menu "$(lat_t choose_option)" 23 76 16 "$@") ; status=$? ;;
 whiptail) result=$(whiptail --title "$title" --menu "$(lat_t choose_option)" 23 76 16 "$@" 3>&1 1>&2 2>&3);status=$? ;;
 *)
  printf '\n==== %s ====\n' "$title" >&2
  local tags=() index=1
  while (( $# >= 2 ));do
   if [[ $1 == 0 ]];then printf '%-3s %s\n' 0 "$2" >&2
   else printf '%-3s %s\n' "$index" "$2" >&2;tags[index]=$1;((index+=1));fi
   shift 2
  done
  printf '%s: ' "$(lat_t choose_option)" >&2
  IFS= read -r result || return 1
  if [[ $result =~ ^[0-9]+$ && $result != 0 ]];then
   ((10#$result<index && 10#$result>0)) || return 1
   result=${tags[10#$result]}
  fi
  status=0;;
 esac
 [[ $status -eq 0 ]] || return 1
 printf '%s\n' "$result"
}
lat_ui_notice() {
 local message=$1
 case "$LAT_UI" in
 zenity) zenity --info --title='Linux Adminw21' --text="$message" --width=480;;
 dialog) dialog --clear --title 'Linux Adminw21' --msgbox "$message" 11 70;;
 whiptail) whiptail --title 'Linux Adminw21' --msgbox "$message" 11 70;;
 *) printf '\n%s\n' "$message";lat_pause;;
 esac
}
lat_ui_show_text() {
 local content=$1
 case "$LAT_UI" in
 zenity) zenity --info --title='Linux Adminw21' --text="$content" --width=680;;
 dialog) dialog --clear --title 'Linux Adminw21' --msgbox "$content" 20 75;;
 whiptail) whiptail --title 'Linux Adminw21' --msgbox "$content" 20 75;;
 *) printf '\n%s\n' "$content";lat_pause;;
 esac
}

lat_ui_input() {
 local title=$1 result status
 case "$LAT_UI" in
 zenity) result=$(zenity --entry --title="Linux Adminw21" --text="$title" --width=550); status=$? ;;
 dialog) result=$(dialog --stdout --title "$title" --inputbox "$title" 10 74) ; status=$? ;;
 whiptail) result=$(whiptail --title "$title" --inputbox "$title" 10 74 3>&1 1>&2 2>&3); status=$? ;;
 *) printf '%s: ' "$title" >&2; IFS= read -r result || return 1; status=0;;
 esac
 [[ $status == 0 && -n $result ]] || return 1
 printf '%s\n' "$result"
}
lat_ui_confirm() {
 local msg=$1 answer
 case "$LAT_UI" in
 zenity) zenity --question --title="Linux Adminw21" --text="$msg" --width=550 ;;
 dialog) dialog --title "Linux Adminw21" --yesno "$msg" 11 72 ;;
 whiptail) whiptail --title "Linux Adminw21" --yesno "$msg" 11 72 ;;
 *) printf '%s [y/N]: ' "$msg" >&2; IFS= read -r answer || return 1; [[ $answer == y || $answer == Y || $answer == j || $answer == J ]] ;;
 esac
}
