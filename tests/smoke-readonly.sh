#!/usr/bin/env bash
set -euo pipefail
nvidia-smi -L
lspci -vv -s 0000:8c:00.0 | grep -E 'LnkSta:|LnkCtl2:|UESta:|CESta:'
journalctl -k -b --no-pager |
grep -Ei 'NVRM.*Xid|CUDA_ERROR|GPPut|nvAssertFailed|Completion Timeout|CmpltTO\+|BadTLP\+|BadDLLP\+|GPU.*fallen off|GPU is lost' || echo "PASS: no critical NVIDIA/PCIe errors"
