# Investigation Log

## Original failure
Before the current workaround, basic CUDA and 256 MiB pageable transfers passed, but a pinned-memory path produced CUDA error 719 followed by a hard host freeze. Post-freeze NVIDIA evidence included a GPFIFO watchdog assertion.

## Firmware update
ASUS BIOS was updated to 3305. Host Barlow Ridge NVM became 59.02. AORUS NVM remained 62.2. Secure Boot/lockdown remained enabled.

With NVIDIA fully blocked, cold boot held Gen4 x4. With normal NVIDIA initialization, runtime often returned to Gen1.

## Eliminated hypotheses
- ASPM disabled.
- L1.1/L1.2 controls disabled.
- NVIDIA DynamicPowerManagement=0 and S0ix=0 did not change behavior.
- Linux PCIe cooling/bwctrl did not explain the hardware target rewrite.
- userspace `setpci` writes failed under lockdown.

## Signed kernel helper
A signed helper was able to perform the guarded PCI operation under lockdown:

```text
initial           0044 / 3044
Gen3+HASD armed   0063 / 3044
single retrain
stable            0063 / 7043
SUCCESS
```

NVIDIA subsequently initialized successfully.

## Runtime scaling
NVIDIA PMU/P-state behavior was observed roughly as:
- P8 -> Gen1
- P5 -> Gen2
- higher performance -> Gen3

This runtime scaling is acceptable. The key workaround is the pre-driver Gen3 ceiling/HASD sequence, not permanent Gen3 idle.

## CUDA validation
The final working configuration passed:
- pageable 4 KiB and 256 MiB
- pinned allocation 4 KiB
- pinned H2D/D2H 4 KiB
- pinned bidirectional 1/64/128/256 MiB
- 20 x 64 MiB pinned bidirectional cycles
- data verification every cycle
- ~3.06 GB/s H2D, ~3.38 GB/s D2H
- no Xid, Completion Timeout, Bad TLP/DLLP, GPU loss, or host freeze

## Cold boot
The final systemd service reached `status=0/SUCCESS`, loaded the signed stabilizer before NVIDIA, then loaded NVIDIA and detected both RTX 2070 and RTX 5090.

Remaining work is packaging/kernel-update survival.
