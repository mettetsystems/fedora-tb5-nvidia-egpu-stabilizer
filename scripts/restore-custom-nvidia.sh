#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
KVER=7.1.10-200.fc44.x86_64
BACKUP=${1:?Pass the backup directory printed by switch-packaged-nvidia.sh}
CUSTOM="/lib/modules/$KVER/updates/nvidia-driver-injector"
[[ -d "$BACKUP/nvidia-driver-injector" && ! -e "$CUSTOM" ]] || { echo 'Backup missing or destination already exists; stopping.'; exit 1; }
cp -a "$BACKUP/nvidia-driver-injector" "$CUSTOM"
depmod -a "$KVER"
modinfo -k "$KVER" -n nvidia
echo 'Custom next-boot module selection restored. No module reload or reboot performed.'
