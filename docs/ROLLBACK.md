# Rollback: restore the validated manual implementation

This procedure restores the Phase C known-good **hand-installed** boot path
from the snapshot taken at the start of Phase D.

Do **not** execute this unless the packaged next-boot path has failed and
you have decided to roll back. Do not run it automatically from RPM
scriptlets, akmods, or systemd.

Do **not** restore leftover injector files. Safety invariant 12.

Do **not** unload `tb5_gen3_pre` or NVIDIA while they are already loaded.
Do **not** write PCI configuration space. Do **not** retrain PCIe.
Do **not** modify GRUB. Do **not** run CUDA as part of rollback.

Snapshot:

```text
/var/lib/tb5-egpu-gen3/rollback/validated-manual-v0.1/
```

Authoritative copies (use these, not `moved-from-live/` for the two
`99-egpu-gen3-preload.conf` files):

```text
lib/modules/7.1.10-200.fc44.x86_64/extra/tb5_gen3_pre.ko
etc/systemd/system/egpu-gen3-preload.service
usr/local/sbin/egpu-gen3-kmod-start
etc/modprobe.d/99-egpu-gen3-preload.conf
etc/dracut.conf.d/99-egpu-gen3-preload.conf
```

`moved-from-live/` flattened two different `99-egpu-gen3-preload.conf`
files to the same basename. Prefer the path-structured copies above.
Verify against `SHA256SUMS` and `MANIFEST.txt` in the snapshot before
copying.

Expected hashes from the snapshot `SHA256SUMS`:

```text
f8246716e57bf97d3bb85e3b4ab2a9200869300128f339dfb3163ff1f2720a3d  .../extra/tb5_gen3_pre.ko
e4cfacfef662f395296c34a3c08789c4db697bb4045e55ccb53721bb7ae28627  .../egpu-gen3-preload.service
ddfafa053c357f360db52a6004407c39905118728c992881e9cb72341e56e59b  .../egpu-gen3-kmod-start
3d47495b38d8564fc8fe5368722d01d3310222356ba0145d32c6dd3b236a9ebb  .../etc/modprobe.d/99-egpu-gen3-preload.conf
229f9c275fa724a7b2a6ac6d6d338e35555afc747dbc7df78542b17fe3dbc321  .../etc/dracut.conf.d/99-egpu-gen3-preload.conf
```

Kernel at snapshot: `7.1.10-200.fc44.x86_64`.
NVIDIA: `610.57.04`. Helper signer: `fedora_1742039933_69145a81`.
Git tag: `phase-c-akmod-v0.2`.

## 1. Restore the manual helper into the module tree

Do not delete the packaged helper unless you are sure you want name
resolution to return to the uncompressed extra/ file.

```bash
RB=/var/lib/tb5-egpu-gen3/rollback/validated-manual-v0.1
KVER="$(uname -r)"
sudo cp -a -- \
  "$RB/lib/modules/${KVER}/extra/tb5_gen3_pre.ko" \
  "/lib/modules/${KVER}/extra/tb5_gen3_pre.ko"
sudo sha256sum "/lib/modules/${KVER}/extra/tb5_gen3_pre.ko"
sudo depmod -a "$KVER"
modinfo -n tb5_gen3_pre
```

`modinfo -n tb5_gen3_pre` should again resolve to
`/lib/modules/${KVER}/extra/tb5_gen3_pre.ko` if that uncompressed file
wins over `extra/tb5-egpu-gen3/tb5_gen3_pre.ko.xz`. If it still points
at the packaged copy, move the packaged file aside into the snapshot
(do not delete it) and run `depmod -a` again.

Do not `modprobe` or `rmmod` the helper.

## 2. Restore the manual systemd unit and start script

```bash
RB=/var/lib/tb5-egpu-gen3/rollback/validated-manual-v0.1
sudo cp -a -- \
  "$RB/etc/systemd/system/egpu-gen3-preload.service" \
  /etc/systemd/system/egpu-gen3-preload.service
sudo cp -a -- \
  "$RB/usr/local/sbin/egpu-gen3-kmod-start" \
  /usr/local/sbin/egpu-gen3-kmod-start
sudo systemctl daemon-reload
sudo systemctl reenable egpu-gen3-preload.service
systemctl cat egpu-gen3-preload.service
systemctl is-enabled egpu-gen3-preload.service
```

`systemctl cat` must show `# /etc/systemd/system/egpu-gen3-preload.service`
and `ExecStart=/usr/local/sbin/egpu-gen3-kmod-start`.

Do **not** `systemctl start` or `restart` the unit on a session where
NVIDIA is already loaded.

## 3. Restore the manual modprobe and dracut snippets

```bash
RB=/var/lib/tb5-egpu-gen3/rollback/validated-manual-v0.1
sudo cp -a -- \
  "$RB/etc/modprobe.d/99-egpu-gen3-preload.conf" \
  /etc/modprobe.d/99-egpu-gen3-preload.conf
sudo cp -a -- \
  "$RB/etc/dracut.conf.d/99-egpu-gen3-preload.conf" \
  /etc/dracut.conf.d/99-egpu-gen3-preload.conf
```

The packaged `/usr/lib/modprobe.d/` and `/usr/lib/dracut/dracut.conf.d/`
snippets remain if `tb5-egpu-gen3` is still installed. Their directives
match the manual blocker; the dracut `install_items` path differs
(`/usr/lib` vs `/etc`). After restoring `/etc`, rebuild initramfs so
the image matches the rollback policy.

Optional: `sudo rpm -e tb5-egpu-gen3` removes only the integration RPM.
That RPM's scriptlets do not disable or stop the service. Do not remove
`akmod-tb5-egpu-gen3` / the kernel-specific kmod unless you also intend
to stop using the packaged `.ko.xz`.

## 4. Rebuild initramfs for the current kernel

Require at least 120 MiB free on `/boot`.

```bash
df -h /boot
sha256sum "/boot/initramfs-$(uname -r).img"
sudo dracut --force \
  "/boot/initramfs-$(uname -r).img" \
  "$(uname -r)"
sha256sum "/boot/initramfs-$(uname -r).img"
sudo lsinitrd "/boot/initramfs-$(uname -r).img" |
  grep -E '99-egpu-gen3-preload|/usr/bin/false|nvidia\.ko'
```

Confirm NVIDIA `.ko` files remain omitted and the blocker plus
`/usr/bin/false` are present.

Do not reboot from this document. Reboot only as an explicit later step.

## 5. What not to restore

Do **not** copy back:

```text
leftover-not-active/usr/local/sbin/egpu-gen3-preload
leftover-not-active/usr/local/bin/egpu-gen3-preload
```

Those are leftover injector artifacts. They are not the validated
workaround.

`adjacent-not-migrated/egpu-wake.service` and
`99-egpu-awake.rules` were never moved. Leave them unless you have a
separate reason to change them.

## 6. After a later approved reboot

If rollback was applied before reboot, the next boot should use
`/usr/local/sbin/egpu-gen3-kmod-start` and the uncompressed extra
`tb5_gen3_pre.ko`. Confirm with `systemctl status`, `modinfo -n`,
`nvidia-smi -L`, and the kernel log. Do not treat idle Gen1 as failure.
