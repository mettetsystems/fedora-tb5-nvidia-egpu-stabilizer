#!/usr/bin/env bash
# Stage RPM sources into an in-tree rpmbuild tree. Does not build or install.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="1.0.0"
TOPDIR="${1:-$ROOT/packaging/rpm/build}"

mkdir -p "$TOPDIR"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

tar -C "$ROOT/src" -czf "$TOPDIR/SOURCES/tb5-egpu-gen3-kmod-${VERSION}.tar.gz" \
    --transform "s,^,tb5-egpu-gen3-kmod-${VERSION}/," \
    Makefile tb5_gen3_pre.c

install -m 644 "$ROOT/packaging/systemd/egpu-gen3-preload.service" "$TOPDIR/SOURCES/"
install -m 755 "$ROOT/packaging/scripts/egpu-gen3-kmod-start" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/packaging/modprobe/99-egpu-gen3-preload.conf" \
    "$TOPDIR/SOURCES/99-egpu-gen3-preload.modprobe.conf"
install -m 644 "$ROOT/packaging/dracut/99-egpu-gen3-preload.conf" \
    "$TOPDIR/SOURCES/99-egpu-gen3-preload.dracut.conf"
install -m 644 "$ROOT/README.md" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/docs/SAFETY_INVARIANTS.md" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/docs/TROUBLESHOOTING.md" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/docs/AKMOD_BUILD.md" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/docs/INVESTIGATION_LOG.md" "$TOPDIR/SOURCES/"
install -m 755 "$ROOT/scripts/collect-support-bundle.sh" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/tests/smoke-readonly.sh" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/tests/cuda_pinned_bidir.py" "$TOPDIR/SOURCES/"
install -m 644 "$ROOT/tests/cuda_validation_harness.py" "$TOPDIR/SOURCES/"

install -m 644 "$ROOT/packaging/rpm/tb5-egpu-gen3-kmod.spec" "$TOPDIR/SPECS/"
install -m 644 "$ROOT/packaging/rpm/tb5-egpu-gen3.spec" "$TOPDIR/SPECS/"

echo "Staged RPM sources in $TOPDIR"
