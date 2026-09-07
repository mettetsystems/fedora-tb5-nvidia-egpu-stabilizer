# Akmod Build and Install Notes

This is the Fedora 44 packaging record for the validated `tb5_gen3_pre` helper.
It does not change GRUB, does not disable Secure Boot/lockdown/IOMMU, and does
not replace NVIDIA modules.

Inspected on this machine:

- `akmods-0.6.2-14.fc44`
- `kmodtool-1.2.1-1.fc44`
- signing macros in `/usr/lib/rpm/macros.d/macros.kmodtool`
- host keys in `/etc/pki/akmods/` (never ship these)

## Package split

- `tb5-egpu-gen3-kmod.spec` produces:
  - `tb5-egpu-gen3-kmod-common` (payload-less; satisfies kmodtool)
  - `akmod-tb5-egpu-gen3`
  - `kmod-tb5-egpu-gen3` (metapackage)
  - later `kmod-tb5-egpu-gen3-<kernel>` from akmods
- `tb5-egpu-gen3.spec` produces boot orchestration only and **Requires**
  `akmod-tb5-egpu-gen3`. It does **not** Provide `tb5-egpu-gen3-kmod-common`.

Dependency direction:

```text
tb5-egpu-gen3-kmod-common
        ^
akmod-tb5-egpu-gen3

tb5-egpu-gen3
        |
        v
akmod-tb5-egpu-gen3
```

The akmod can be installed without the integration RPM.

kmodtool Requires `%{pkg_kmod_name}-common`. With `--kmodname tb5-egpu-gen3-kmod`
that name is `tb5-egpu-gen3-kmod-common`.

## Akmod `%posttrans`

Installing `akmod-tb5-egpu-gen3` runs, from the kmodtool-generated scriptlet:

```bash
nohup /usr/sbin/akmods --from-akmod-posttrans --akmod tb5-egpu-gen3 &> /dev/null &
```

That starts a **background** rebuild. Do not run a second `akmods --force`
until that job has finished. Phase C should install only
`tb5-egpu-gen3-kmod-common` plus `akmod-tb5-egpu-gen3`, then wait for the
posttrans build (or inspect `/var/cache/akmods` / `modinfo`) before any
manual akmods invocation. No concurrent akmods builds.

## Integration RPM is inert

`tb5-egpu-gen3` scriptlets do not call `systemctl` and do not use
`%systemd_post` / `%systemd_preun` / `%systemd_postun`. Installing or
removing it must not preset, enable, disable, start, or stop
`egpu-gen3-preload.service`, including the live hand-installed unit at
`/etc/systemd/system/egpu-gen3-preload.service`.

Daemon-reload and activation stay an explicit operator step after the
helper is built, signed, and initramfs-validated. See
`scripts/uninstall-local.sh` for service migration; do not rely on RPM
scriptlets to touch the active boot path.

## Safety

Never run `tests/cuda_pinned_bidir.py` or `tests/cuda_validation_harness.py`
from RPM `%check`, akmods, systemd, or the install scripts. They are manual
diagnostics only. `cuda_pinned_bidir.py` is the historical one-shot test;
`cuda_validation_harness.py` is a reconstructed ladder, not the recorded
validation script.

Do not reboot from these tools. Do not retrain PCIe. Do not enable or start
`egpu-gen3-preload.service` until package, module, signature, and initramfs
validation are complete. The integration RPM does not preset or enable the
unit.

The packaged unit has `After=akmods.service`. That only waits for the
akmods service to exit if it was started this boot. It does **not** mean
`tb5_gen3_pre` was built or signed for this kernel. If the helper is
missing, `egpu-gen3-kmod-start` must fail closed and leave NVIDIA blocked.
Do not "fix" that by retraining, loading NVIDIA early, or disabling Secure
Boot. Build the helper first, then reboot into a kernel that has it.

## Phase B (build only; not yet approved)

From the repository root, using an in-tree rpmbuild directory (does not install):

```bash
chmod +x packaging/rpm/prepare-sources.sh
./packaging/rpm/prepare-sources.sh

rpmbuild \
  --define "_topdir $PWD/packaging/rpm/build" \
  -ba "$PWD/packaging/rpm/build/SPECS/tb5-egpu-gen3-kmod.spec"

rpmbuild \
  --define "_topdir $PWD/packaging/rpm/build" \
  -ba "$PWD/packaging/rpm/build/SPECS/tb5-egpu-gen3.spec"
```

Do not add `--rebuild` of initramfs, `akmods --force`, `rpm -i`, `modprobe`, or `dnf install` until a later phase is approved.

After a future approved install of the **akmod** (not the integration RPM),
wait for the kmodtool `%posttrans` background `akmods --from-akmod-posttrans`
job to finish. Only then, if still needed:

```bash
sudo akmods --force --kernels "$(uname -r)" --akmod tb5-egpu-gen3
modinfo tb5_gen3_pre
```

Confirm the signer is the enrolled akmods certificate before any reboot.

## Kernel update

1. Install the new kernel and matching `kernel-devel`.
2. Wait for `akmods` to **successfully** build and sign `tb5_gen3_pre` for that kernel. `After=akmods.service` is not this step.
3. Confirm `modinfo -k <new-kver> tb5_gen3_pre` shows a signature.
4. Only then reboot into the new kernel.
5. If the helper is missing, NVIDIA stays blocked by the packaged `install ... /usr/bin/false` rules. That is fail-closed, not a reason to retrain or to disable Secure Boot.

## Enabling the packaged service

The integration RPM only drops the unit file. It does not enable it.
After a later approved migration (not Phase C as first proposed):

```bash
sudo systemctl daemon-reload
sudo systemctl enable egpu-gen3-preload.service
```

Do not `systemctl start` it on a session where NVIDIA is already loaded. The next validated reboot is what activates the boot path.

## Uninstall / rollback

RPM removal of `tb5-egpu-gen3` does **not** `systemctl disable --now` and
will not disturb `/etc/systemd/system/egpu-gen3-preload.service`.
Service deactivation is explicit in `scripts/uninstall-local.sh`
(`--deactivate-packaged-service`), which refuses if the hand-installed
`/etc` unit still exists.

```bash
./scripts/uninstall-local.sh
sudo ./scripts/uninstall-local.sh --apply --rebuild-initramfs
```

Do not restore `/usr/local/sbin/egpu-gen3-preload`. Rebuild initramfs only after `/boot` has enough free space. Do not reboot from the script.

## `/boot` space

Dracut needs a spare initramfs-sized window. The install/uninstall scripts refuse dracut below 120 MiB free. Remove old kernels with DNF rather than deleting files by hand.
