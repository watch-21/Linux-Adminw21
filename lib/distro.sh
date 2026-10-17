#!/usr/bin/env bash
# shellcheck disable=SC2034 # Shared detection results consumed by other modules.
# Distribution detection is read-only. Never execute values from os-release.
lat_detect_distro() {
 LAT_DISTRO=unknown LAT_DISTRO_ID=unknown LAT_DISTRO_LIKE='' LAT_PKGMGR=none
 LAT_DISTRO_VERSION=unknown LAT_DISTRO_SUPPORTED=no
 local release_file=${LAT_OS_RELEASE_FILE:-/etc/os-release}
 local line value name='' id='' like='' version=''
 if [[ -r $release_file ]]; then
  while IFS= read -r line || [[ -n $line ]]; do
   case $line in
    ID=*|ID_LIKE=*|PRETTY_NAME=*|VERSION_ID=*)
      value=${line#*=}
      if [[ $value == \"*\" ]]; then value=${value:1:${#value}-2}; fi
      if [[ $value == \'*\' ]]; then value=${value:1:${#value}-2}; fi
      case $line in
       ID=*) id=$value ;;
       ID_LIKE=*) like=$value ;;
       PRETTY_NAME=*) name=$value ;;
       VERSION_ID=*) version=$value ;;
      esac;;
   esac
  done < "$release_file"
 fi
 LAT_DISTRO_ID=${id:-unknown}
 LAT_DISTRO_LIKE=$like
 LAT_DISTRO=${name:-$LAT_DISTRO_ID}
 LAT_DISTRO_VERSION=${version:-unknown}
 # Pick package tools only when the distro family matches. Do not assume that
 # merely finding 'apt' or 'dnf' makes it safe to use on another distro.
 local family=" $LAT_DISTRO_ID $LAT_DISTRO_LIKE "
 case " $LAT_DISTRO_ID " in
  ' alpine ') lat_command_exists apk && LAT_PKGMGR=apk ;;
  ' void ') lat_command_exists xbps-install && LAT_PKGMGR=xbps ;;
  ' gentoo ') lat_command_exists emerge && LAT_PKGMGR=portage ;;
  ' nixos ') lat_command_exists nix && LAT_PKGMGR=nix ;;
  ' slackware ') lat_command_exists slackpkg && LAT_PKGMGR=slackpkg ;;
  ' solus ') lat_command_exists eopkg && LAT_PKGMGR=eopkg ;;
 esac
 if [[ $LAT_PKGMGR == none ]]; then
  case $family in
   *' debian '*|*' ubuntu '*) lat_command_exists apt-get && LAT_PKGMGR=apt ;;
   *' arch '*) lat_command_exists pacman && LAT_PKGMGR=pacman ;;
   *' fedora '*|*' rhel '*|*' centos '*)
     if lat_command_exists dnf; then LAT_PKGMGR=dnf
     elif lat_command_exists yum; then LAT_PKGMGR=yum; fi ;;
   *' suse '*|*' opensuse '*) lat_command_exists zypper && LAT_PKGMGR=zypper ;;
   *' mandriva '*|*' mageia '*)
     if lat_command_exists dnf; then LAT_PKGMGR=dnf
     elif lat_command_exists urpmi; then LAT_PKGMGR=urpmi; fi ;;
  esac
 fi
 # A distro may be detected even without its package manager installed.
 if [[ $LAT_PKGMGR != none ]]; then LAT_DISTRO_SUPPORTED=detected; fi
 return 0
}
