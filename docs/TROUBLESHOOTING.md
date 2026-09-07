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
sudo akmods --force --kernels "$(uname -r)"
find /var/cache/akmods -type f -name '*.failed.log' -print
modinfo tb5_gen3_pre
```

Verify the module is built and signed first.

## `/boot` full
Dracut needs room for a temporary initramfs. Remove genuinely old kernels through DNF; do not manually delete random boot files.
