# Troubleshooting

## NVIDIA loaded before stabilizer
Do not retrain manually. Check:

```bash
lsmod | grep '^nvidia'
systemctl status egpu-gen3-preload.service
journalctl -b -u egpu-gen3-preload.service
```

## `setpci`: Operation not permitted
Expected under Secure Boot/kernel lockdown for these writes. Keep Secure Boot enabled and use the signed helper.

## Idle link is Gen1
Expected under NVIDIA PMU/P-state scaling. Validate workload behavior and error logs rather than forcing permanent Gen3.

## akmods fails after a kernel update
Do not reboot blindly:

```bash
sudo akmods --force --kernels "$(uname -r)" --akmod tb5-egpu-gen3
find /var/cache/akmods -type f -name '*.failed.log' -print
modinfo tb5_gen3_pre
```

Verify the module is built and signed first. See `docs/AKMOD_BUILD.md`.

## Packaged vs hand-installed paths
The live validated install still uses `/usr/local/sbin` and `/etc`. The packaged layout (not deployed in Phase A) is:

- `/usr/libexec/tb5-egpu-gen3/egpu-gen3-kmod-start`
- `/usr/lib/systemd/system/egpu-gen3-preload.service`
- `/usr/lib/modprobe.d/99-egpu-gen3-preload.conf`
- `/usr/lib/dracut/dracut.conf.d/99-egpu-gen3-preload.conf`

Do not start the packaged oneshot while NVIDIA is already loaded. The
integration RPM does not preset, enable, disable, start, or stop the unit.
Enable it only after helper build, signature, and initramfs validation,
using an explicit operator command—not RPM scriptlets.

Installing or removing `tb5-egpu-gen3` must not disturb
`/etc/systemd/system/egpu-gen3-preload.service`.

`After=akmods.service` does not mean the new kernel already has a signed
`tb5_gen3_pre`. If `modprobe tb5_gen3_pre` fails, the start script must fail
closed and must not load NVIDIA.

## `/boot` full
Dracut needs room for a temporary initramfs. Remove genuinely old kernels through DNF; do not manually delete random boot files.
