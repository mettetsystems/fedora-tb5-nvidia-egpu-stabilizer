#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-$PWD/tb5-egpu-support-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
run(){ name="$1"; shift; { echo "\$ $*"; "$@"; } >"$OUT/$name.txt" 2>&1 || true; }
run uname uname -a
run cmdline cat /proc/cmdline
run nvidia-smi nvidia-smi
run modules lsmod
run helper-modinfo modinfo tb5_gen3_pre
run nvidia-modinfo modinfo nvidia
run service systemctl --no-pager -l status egpu-gen3-preload.service
run service-journal journalctl -b -u egpu-gen3-preload.service --no-pager
run bridge lspci -vvv -s 0000:8c:00.0
run gpu lspci -vvv -s 0000:8d:00.0
cp -a /etc/modprobe.d/99-egpu-gen3-preload.conf "$OUT/" 2>/dev/null || true
cp -a /etc/dracut.conf.d/99-egpu-gen3-preload.conf "$OUT/" 2>/dev/null || true
cp -a /etc/systemd/system/egpu-gen3-preload.service "$OUT/" 2>/dev/null || true
cp -a /usr/local/sbin/egpu-gen3-kmod-start "$OUT/" 2>/dev/null || true
echo "Support bundle: $OUT"
