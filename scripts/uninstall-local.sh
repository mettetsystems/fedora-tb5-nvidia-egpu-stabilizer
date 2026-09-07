#!/usr/bin/env bash
# Restore ordinary NVIDIA boot behavior for the packaged stabilizer.
# Default is dry-run. Does not reboot, retrain, touch GRUB, run CUDA,
# or restore the old injector.
set -euo pipefail

BOOT_MIN_KIB=$((120 * 1024))
APPLY=0
DRACUT=0
DEACTIVATE=0

usage() {
    cat <<'EOF'
Usage: uninstall-local.sh [--apply] [--rebuild-initramfs]

Default: print the uninstall plan and refuse to change the system.

  --apply               remove tb5-egpu-gen3* RPMs if installed.
                        Does not systemctl enable/disable/start/stop/preset.
  --deactivate-packaged-service
                        with --apply, disable the packaged unit only if
                        /etc/systemd/system/egpu-gen3-preload.service is
                        absent. Refuses if the hand-installed /etc unit exists.
  --rebuild-initramfs   with --apply, run dracut -f after a /boot free-space
                        check so NVIDIA can return to the initramfs

Never:
  - reboot
  - retrain PCIe
  - modify GRUB
  - run CUDA tests
  - restore /usr/local/sbin/egpu-gen3-preload
  - unload/reload NVIDIA as a workaround
EOF
}

log() { echo "uninstall-local: $*"; }
die() { echo "uninstall-local: ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply) APPLY=1; shift ;;
        --deactivate-packaged-service) DEACTIVATE=1; shift ;;
        --rebuild-initramfs) DRACUT=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

boot_kib_free() {
    df -Pk /boot | awk 'NR==2 {print $4}'
}

plan() {
    cat <<EOF
uninstall-local plan
  apply:            $APPLY
  deactivate-svc:   $DEACTIVATE
  rebuild-initramfs:$DRACUT
  /boot free KiB:   $(boot_kib_free)  (need >= ${BOOT_MIN_KIB} for dracut)

Will remove, if installed:
  tb5-egpu-gen3
  tb5-egpu-gen3-kmod-common
  akmod-tb5-egpu-gen3
  kmod-tb5-egpu-gen3
  kmod-tb5-egpu-gen3-\$(uname -r)
  tb5-egpu-gen3-kmod

RPM removal does not systemctl the unit. Hand-installed
/etc/systemd/system/egpu-gen3-preload.service is left alone.

Will not restore:
  /usr/local/sbin/egpu-gen3-preload
  any old injector configuration

Hand-installed files under /etc and /usr/local remain unless RPM-owned.
After RPM removal, NVIDIA autoload works only once the omit/blacklist
files are gone AND initramfs is rebuilt.
EOF
}

plan

if [[ "$APPLY" -eq 0 ]]; then
    log "dry-run only; pass --apply to remove packages"
    exit 0
fi

[[ "$(id -u)" -eq 0 ]] || die "--apply must run as root"

if [[ "$DRACUT" -eq 1 && "$(boot_kib_free)" -lt "$BOOT_MIN_KIB" ]]; then
    die "/boot free space is below ${BOOT_MIN_KIB} KiB; refusing dracut"
fi

if [[ "$DEACTIVATE" -eq 1 ]]; then
    if [[ -e /etc/systemd/system/egpu-gen3-preload.service ]]; then
        die "hand-installed /etc/systemd/system/egpu-gen3-preload.service exists; refusing to disable the unit"
    fi
    if [[ -e /usr/lib/systemd/system/egpu-gen3-preload.service ]]; then
        log "disabling packaged unit only (no --now)"
        systemctl disable egpu-gen3-preload.service
    else
        log "no packaged unit file; skip disable"
    fi
fi

mapfile -t PKGS < <(rpm -qa 'tb5-egpu-gen3*' 'akmod-tb5-egpu-gen3' 'kmod-tb5-egpu-gen3*' | sort -u || true)
if [[ ${#PKGS[@]} -gt 0 ]]; then
    log "removing:"
    printf '  %s\n' "${PKGS[@]}"
    rpm -e "${PKGS[@]}"
else
    log "no tb5-egpu-gen3 RPMs installed"
fi

if [[ -e /usr/local/sbin/egpu-gen3-preload ]]; then
    log "NOTE: leaving /usr/local/sbin/egpu-gen3-preload in place (do not restore injector)"
fi

if [[ "$DRACUT" -eq 1 ]]; then
    log "rebuilding initramfs for $(uname -r)"
    dracut -f --kver "$(uname -r)"
    log "initramfs rebuilt. Do not reboot until you inspect the image and unit state."
else
    log "skipped dracut. NVIDIA may still be omitted from the current initramfs."
fi

log "Done. Do not reboot from this script. Do not retrain PCIe."
