#!/usr/bin/env bash
# Change next-boot module selection only. Does not unload modules or reboot.
set -Eeuo pipefail
trap 'rc=$?; printf "Stopped at line %s (exit %s): %s\n" "$LINENO" "$rc" "$BASH_COMMAND" >&2' ERR
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
KVER=7.1.10-200.fc44.x86_64
[[ $(uname -r) == "$KVER" ]] || { echo 'Kernel changed; review before proceeding.'; exit 1; }
MODROOT="/lib/modules/$KVER"
CUSTOM="$MODROOT/updates/nvidia-driver-injector"
PKG="kmod-nvidia-$KVER-610.57.04-1.fc44.x86_64"
[[ -d "$CUSTOM" ]] || { echo 'Custom module directory absent; nothing changed.'; exit 1; }
[[ $(modinfo -n nvidia) == "$CUSTOM/nvidia.ko" ]] || { echo 'Unexpected module selection.'; exit 1; }
VERIFY=$(rpm -V "$PKG") || { echo "Package verification failed: $VERIFY"; exit 1; }
[[ -z "$VERIFY" ]] || { echo "$VERIFY"; exit 1; }
echo 'Checking Secure Boot key enrollment...'
if mokutil --test-key /etc/pki/akmods/certs/public_key.der; then
    echo 'Key check passed.'
else
    rc=$?
    echo "mokutil returned $rc; stopping before changes. Please share this output."
    exit "$rc"
fi
[[ $(modinfo -F signer "$MODROOT/extra/nvidia/nvidia.ko.xz") == $(modinfo -F signer "$CUSTOM/nvidia.ko") ]] || { echo 'Module signers differ; inspect signing before proceeding.'; exit 1; }
echo 'Checking stabilizer enablement...'
systemctl is-enabled egpu-gen3-preload.service
IMAGE="/boot/initramfs-$KVER.img"
echo "Inspecting initramfs: $IMAGE"
CONTENTS=$(lsinitrd "$IMAGE")
if grep -E '/nvidia([_-](drm|modeset|uvm|peermem))?\.ko' <<< "$CONTENTS" >/dev/null; then
    echo 'Initramfs contains NVIDIA modules; separate rebuild review required.'; exit 1
fi
grep '99-egpu-gen3-preload.conf' <<< "$CONTENTS" || { echo 'Required initramfs blocker missing; stopping before changes.'; exit 1; }
BACKUP="/var/lib/tb5-egpu-gen3/rollback/packaged-driver-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
chmod 700 "$BACKUP"
cp -a "$IMAGE" "$BACKUP/initramfs.img"
cp -a "$CUSTOM" "$BACKUP/nvidia-driver-injector"
tar -cpf "$BACKUP/boot-config.tar" /etc/modprobe.d /etc/dracut.conf.d /etc/depmod.d /etc/default/grub /etc/systemd/system /boot/loader/entries /usr/lib/modprobe.d/99-egpu-gen3-preload.conf /usr/lib/dracut/dracut.conf.d/99-egpu-gen3-preload.conf
cat /proc/cmdline > "$BACKUP/cmdline"
systemctl cat egpu-gen3-preload.service > "$BACKUP/stabilizer.service"
rpm -qa > "$BACKUP/packages.txt"
# Keep a second copy outside the module search tree until verification succeeds.
mv "$CUSTOM" "$BACKUP/removed-modules"
restore_on_failure() {
    echo 'Selection verification failed; restoring custom modules.' >&2
    mv "$BACKUP/removed-modules" "$CUSTOM"
    depmod -a "$KVER"
}
trap restore_on_failure ERR
depmod -a "$KVER"
for name in nvidia nvidia_modeset nvidia_uvm nvidia_drm nvidia_peermem; do
    selected=$(modinfo -n "$name")
    [[ "$selected" == "$MODROOT/extra/nvidia/"* ]]
    printf '%s -> %s\n' "$name" "$selected"
done
trap - ERR
printf '\nBackup: %s\nNext-boot selection verified. Live modules are unchanged. No reboot performed.\n' "$BACKUP"
printf 'Rollback before reboot: sudo bash %q %q\n' "$(dirname "$0")/restore-custom-nvidia.sh" "$BACKUP"
