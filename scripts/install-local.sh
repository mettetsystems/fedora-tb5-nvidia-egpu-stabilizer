#!/usr/bin/env bash
# Stage and (optionally) install the local TB5 stabilizer RPMs.
# Default is dry-run. Does not reboot, retrain, touch GRUB, run CUDA,
# unload NVIDIA, or load/unload tb5_gen3_pre.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="1.0.0"
RELEASE_DIST=""
TOPDIR="$ROOT/packaging/rpm/build"
BOOT_MIN_KIB=$((120 * 1024))
APPLY=0

usage() {
    cat <<'EOF'
Usage: install-local.sh [--apply]

Default: print the install plan and refuse to change the system.

  --apply   install already-built RPMs from packaging/rpm/build/RPMS
            and run akmods for the current kernel. Still does not:
              - reboot
              - rebuild initramfs
              - enable or start egpu-gen3-preload.service
              - run CUDA tests
              - unload/reload NVIDIA or tb5_gen3_pre
              - write PCI configuration space
              - modify GRUB

Initramfs rebuild remains a later, explicit step after /boot space is checked.
EOF
}

log() { echo "install-local: $*"; }
die() { echo "install-local: ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply) APPLY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

boot_kib_free() {
    df -Pk /boot | awk 'NR==2 {print $4}'
}

plan() {
    cat <<EOF
install-local plan
  repo:    $ROOT
  topdir:  $TOPDIR
  apply:   $APPLY

Packages expected from Phase B:
  $TOPDIR/RPMS/x86_64/akmod-tb5-egpu-gen3-${VERSION}-*.rpm
  $TOPDIR/RPMS/noarch/tb5-egpu-gen3-${VERSION}-*.rpm
  (and the kmodtool metapackage / main NVRA from the same build)

Then:
  1. rpm -i those RPMs (never --nodeps for NVIDIA/kernel packages)
  2. akmods --force --kernels "\$(uname -r)" --akmod tb5-egpu-gen3
  3. verify modinfo tb5_gen3_pre signer is the enrolled akmods certificate
  4. STOP. Do not reboot, dracut, or start the oneshot here.

Hand-installed live files that must not be deleted by this script:
  /lib/modules/\$(uname -r)/extra/tb5_gen3_pre.ko
  /etc/modprobe.d/99-egpu-gen3-preload.conf
  /etc/dracut.conf.d/99-egpu-gen3-preload.conf
  /etc/systemd/system/egpu-gen3-preload.service
  /usr/local/sbin/egpu-gen3-kmod-start
  /usr/local/sbin/egpu-gen3-preload   (old injector; do not restore)

 /boot free KiB: $(boot_kib_free)  (dracut later needs >= ${BOOT_MIN_KIB})
EOF
}

plan

if [[ "$APPLY" -eq 0 ]]; then
    log "dry-run only; pass --apply to install built RPMs"
    exit 0
fi

[[ "$(id -u)" -eq 0 ]] || die " --apply must run as root"
[[ -x "$ROOT/packaging/rpm/prepare-sources.sh" ]] || die "missing prepare-sources.sh"

if [[ -e /etc/systemd/system/egpu-gen3-preload.service ]]; then
    die "hand-installed /etc/systemd/system/egpu-gen3-preload.service exists; refusing to overlay the live unit"
fi
if [[ -e /usr/local/sbin/egpu-gen3-kmod-start ]]; then
    log "NOTE: /usr/local/sbin/egpu-gen3-kmod-start still exists; packaged helper uses /usr/libexec/tb5-egpu-gen3/"
fi

mapfile -t RPMS < <(find "$TOPDIR/RPMS" -type f -name '*.rpm' ! -name '*.src.rpm' | sort || true)
[[ ${#RPMS[@]} -gt 0 ]] || die "no built RPMs under $TOPDIR/RPMS; run Phase B first"

log "installing:"
printf '  %s\n' "${RPMS[@]}"
rpm -ivh "${RPMS[@]}"

log "building helper for $(uname -r) via akmods"
akmods --force --kernels "$(uname -r)" --akmod tb5-egpu-gen3

log "modinfo tb5_gen3_pre:"
modinfo tb5_gen3_pre || die "helper not visible to modinfo yet"

if [[ "$(boot_kib_free)" -lt "$BOOT_MIN_KIB" ]]; then
    log "WARNING: /boot free space is below ${BOOT_MIN_KIB} KiB; do not run dracut"
else
    log "/boot space looks sufficient for a later explicit dracut"
fi

log "SUCCESS so far. Do not reboot. Do not enable or start egpu-gen3-preload.service."
log "Do not rebuild initramfs until that later phase is approved."
log "Do not run tests/cuda_pinned_bidir.py from this script."
