#!/bin/sh
# Fetch the installer from the latest stable GitHub release.
install_minecraft() (
    set -eu
    workdir=$(mktemp -d)
    trap 'rm -rf -- "$workdir"' EXIT
    installer="$workdir/install-minecraft-couchcraft.py"

    curl -fsSL https://github.com/Thomson67/minecraft-couchcraft-batocera/releases/latest/download/install-minecraft-couchcraft.py -o "$installer"
    python3 "$installer"
)

install_minecraft
