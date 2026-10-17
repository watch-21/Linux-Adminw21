#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "$ROOT/lib/common.sh"
source "$ROOT/lib/distro.sh"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
export LAT_OS_RELEASE_FILE="$TMP/os-release"
# Simulate installed managers without relying on the runner's distro.
lat_command_exists() { case "$1" in apt-get|dnf|yum|pacman|zypper|apk|xbps-install|emerge|nix|slackpkg|eopkg|urpmi) return 0;; *) return 1;;esac; }
check() {
 local id=$1 like=$2 expected=$3
 printf 'ID=%s\nID_LIKE="%s"\nPRETTY_NAME="Fixture %s"\nVERSION_ID="1"\n' "$id" "$like" "$id" > "$LAT_OS_RELEASE_FILE"
 lat_detect_distro
 [[ $LAT_PKGMGR == "$expected" ]] || { echo "FAIL $id $like: expected $expected, got $LAT_PKGMGR" >&2; exit 1; }
}
check ubuntu debian apt
check linuxmint 'ubuntu debian' apt
check debian '' apt
check fedora '' dnf
check rocky rhel dnf
check almalinux 'rhel fedora' dnf
check arch '' pacman
check manjaro arch pacman
check opensuse-tumbleweed 'suse opensuse' zypper
check alpine '' apk
check void '' xbps
check gentoo '' portage
check nixos '' nix
check slackware '' slackpkg
check solus '' eopkg
check unknown '' none
# Missing tools must leave the manager unconfigured.
lat_command_exists() { return 1; }
check ubuntu debian none
echo 'PASS: 16 distro/package-manager fixtures and missing-manager safety'
