#!/usr/bin/env bash
# fetch-patches.sh: descarga el parche BORE de CachyOS para linux-nexora.
set -euo pipefail
KVER=${1:-6.14}
URL="https://github.com/CachyOS/kernel-patcher/raw/master/bore_patches/${KVER}/bore.patch"
mkdir -p "$(dirname "$0")/patches"
curl -fL "$URL" -o "$(dirname "$0")/patches/bore.patch"
echo "[kernel] parche BORE ${KVER} descargado"
