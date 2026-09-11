#!/usr/bin/env bash
# Explicit operator repair for this machine's validated TB5 boot configuration.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run this script with sudo.'; exit 1; }
KVER=$(uname -r)
GPU=/sys/bus/pci/devices/0000:8d:00.0
BRIDGE=/sys/bus/pci/devices/0000:8c:00.0
[[ $(cat "$GPU/vendor") == 0x10de && $(cat "$GPU/device") == 0x2b85 ]]
[[ $(cat "$BRIDGE/vendor") == 0x8086 && $(cat "$BRIDGE/device") == 0x5786 ]]
[[ $(dirname "$(readlink -f "$GPU")") == "$(readlink -f "$BRIDGE")" ]]
for module in nvidia tb5_gen3_pre; do
    [[ $(modinfo -k "$KVER" -F vermagic "$module") == "$KVER "* ]]
    [[ -n $(modinfo -k "$KVER" -F signer "$module") ]]
done
grubby --info="/boot/vmlinuz-$KVER" >/dev/null
BACKUP=$(mktemp -d /var/tmp/egpu-boot-backup.XXXXXXXX)
cp -a /etc/default/grub "$BACKUP/grub"
cp -a /etc/kernel/cmdline "$BACKUP/cmdline"
cp -a /boot/loader/entries "$BACKUP/entries"
[[ ! -e /boot/grub2/grubenv ]] || cp -a /boot/grub2/grubenv "$BACKUP/grubenv"
grubby --info=ALL >"$BACKUP/boot-entries-before.txt"
echo "Backup: $BACKUP"
ARGS='iommu=pt hpbussize=0x20 pcie_aspm=off pcie_ports=native pcie_port_pm=off thunderbolt.host_reset=false pci=realloc,assign-busses,resource_alignment=35@0000:8c:00.0'
# Keep older kernel entries available unchanged for recovery.
grubby --update-kernel="/boot/vmlinuz-$KVER" --no-etc-grub-update \
    --remove-args='iommu hpbussize pcie_aspm pcie_ports pcie_port_pm thunderbolt.host_reset pci' \
    --args="$ARGS"
python3 - "$ARGS" <<'PY'
import pathlib, re, shlex, sys
required = sys.argv[1].split()
keys = {arg.split('=', 1)[0] for arg in required}
def update(value):
    return ' '.join([arg for arg in value.split() if arg.split('=', 1)[0] not in keys] + required)
p = pathlib.Path('/etc/kernel/cmdline')
p.write_text(update(p.read_text().strip()) + '\n')
p = pathlib.Path('/etc/default/grub')
text = p.read_text()
pattern = r'^GRUB_CMDLINE_LINUX=(.*)$'
matches = list(re.finditer(pattern, text, re.M))
if len(matches) != 1:
    raise SystemExit('Expected one GRUB_CMDLINE_LINUX; inspect backup before continuing')
value = shlex.split(matches[0].group(1))
if len(value) != 1:
    raise SystemExit('Unexpected GRUB_CMDLINE_LINUX format')
new_value = update(value[0])
escaped = new_value.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
p.write_text(text[:matches[0].start()] + 'GRUB_CMDLINE_LINUX="' + escaped + '"' + text[matches[0].end():])
PY
grubby --info="/boot/vmlinuz-$KVER" >"$BACKUP/boot-entry-after.txt"
python3 - "$BACKUP/boot-entry-after.txt" "$ARGS" <<'PY'
import pathlib, shlex, sys
line = next(x for x in pathlib.Path(sys.argv[1]).read_text().splitlines() if x.startswith('args='))
actual = shlex.split(line[5:])[0].split()
for arg in sys.argv[2].split():
    assert arg in actual, f'Missing boot argument: {arg}'
print('Verified current kernel boot arguments.')
PY
systemctl is-enabled egpu-gen3-preload.service
echo 'Boot configuration repaired. No live driver changes were made.'
echo 'Reboot when ready, then check: nvidia-smi; systemctl status egpu-gen3-preload.service'
