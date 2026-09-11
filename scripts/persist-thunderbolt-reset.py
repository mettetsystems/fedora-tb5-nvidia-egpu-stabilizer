#!/usr/bin/env python3
"""Preserve the verified host-reset workaround for future kernel installs."""
import os
from pathlib import Path
import re
import shutil
import tempfile

ARG = 'thunderbolt.host_reset=false'

def update(value):
    return ' '.join([x for x in value.split()
                     if not x.startswith('thunderbolt.host_reset=')] + [ARG])

def prepare(cmdline, grub):
    pattern = r'^(GRUB_CMDLINE_LINUX=")(.*)(")$'
    matches = list(re.finditer(pattern, grub, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError('Expected one double-quoted GRUB_CMDLINE_LINUX line')
    match = matches[0]
    revised = grub[:match.start()] + match[1] + update(match[2]) + match[3] + grub[match.end():]
    return update(cmdline.strip()) + '\n', revised

def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo python3.')
    paths = [Path('/etc/kernel/cmdline'), Path('/etc/default/grub')]
    before = [p.read_text() for p in paths]
    after = prepare(*before)
    backup = Path(tempfile.mkdtemp(prefix='thunderbolt-reset-backup-', dir='/var/tmp'))
    for p in paths:
        shutil.copy2(p, backup / p.name)
    print(f'Backup: {backup}', flush=True)
    try:
        # Write cmdline last: Fedora checks its timestamp against default/grub.
        for i in (1, 0):
            paths[i].write_text(after[i])
        for p, expected in zip(paths, after):
            if p.read_text() != expected:
                raise RuntimeError(f'Verification failed: {p}')
    except Exception:
        for p in paths:
            shutil.copy2(backup / p.name, p)
        raise
    print('Verified thunderbolt.host_reset=false in both future-kernel defaults.')
    print('Existing boot entries unchanged. No reboot needed for this defaults update.')

if __name__ == '__main__':
    main()
