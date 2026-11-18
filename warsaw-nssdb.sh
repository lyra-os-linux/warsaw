#!/bin/sh
# Make the Warsaw CA reach Chromium in accounts without ~/.pki/nssdb (warsaw#22).
#
# Chromium uses ~/.pki/nssdb when it exists; otherwise it creates and uses
# ${XDG_DATA_HOME:-~/.local/share}/pki/nssdb. The Warsaw core only writes its
# CA to ~/.pki/nssdb and never creates it. Point the legacy path at the XDG
# database so both programs use the same NSS database.
set -eu

legacy="$HOME/.pki/nssdb"
xdg="${XDG_DATA_HOME:-$HOME/.local/share}/pki/nssdb"

# An existing directory or link (even a broken one) belongs to the user.
if [ -e "$legacy" ] || [ -L "$legacy" ]; then
    exit 0
fi

if [ ! -d "$xdg" ]; then
    mkdir -p -m 0700 "$xdg"
    certutil -N -d "sql:$xdg" --empty-password
fi

mkdir -p -m 0700 "$HOME/.pki"
ln -s "$xdg" "$legacy"
