#!/bin/bash
# Run as the target account via runuser, never as root.
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
((EUID!=0))||exit 77
home=${1:-};key=${2:-};operation=${3:-}
[[ $home == "/home/$(id -un)" && $(getent passwd "$(id -un)"|cut -d: -f6) == "$home" ]]||exit 2
[[ $operation == add || $operation == remove ]]||exit 2
[[ $key =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521))[[:space:]][A-Za-z0-9+/=]+([[:space:]][^[:cntrl:]]*)?$ ]]||exit 2
for p in "$home" "$home/.ssh" "$home/.ssh/authorized_keys";do [[ ! -L $p ]]||exit 2;done
command -v ssh-keygen >/dev/null || exit 69
printf '%s\n' "$key" | ssh-keygen -l -f /dev/stdin >/dev/null 2>&1 || exit 2
umask 077
mkdir -p -- "$home/.ssh"
chmod 700 -- "$home/.ssh"
tmp=$(mktemp "$home/.ssh/.keys.XXXXXXXX")
trap 'rm -f -- "$tmp" "$tmp.new"' EXIT
[[ ! -f $home/.ssh/authorized_keys ]]||cat -- "$home/.ssh/authorized_keys" >"$tmp"
if [[ $operation == add ]];then
 grep -Fxq -- "$key" "$tmp" || printf '%s\n' "$key" >>"$tmp"
else
 grep -Fxv -- "$key" "$tmp" >"$tmp.new" || :
 mv -- "$tmp.new" "$tmp"
fi
chmod 600 "$tmp"
mv -T -- "$tmp" "$home/.ssh/authorized_keys"
echo 'Authorized keys updated as the target account'
