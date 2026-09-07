# TB5 RTX 5090 Fedora Stabilizer

This repository captures a validated Fedora 44 workaround for an AORUS RTX 5090 AI BOX connected through Intel Barlow Ridge / Thunderbolt 5 / USB4.

## Validated baseline

- Fedora 44
- Kernel: `7.1.10-200.fc44.x86_64`
- NVIDIA: `610.57.04`
- ASUS ProArt Z890-CREATOR WIFI BIOS: `3305`
- Host Barlow Ridge NVM: `59.02`
- AORUS AI Box NVM: `62.2`
- Secure Boot enabled; kernel lockdown integrity
- RTX 5090: `10de:2b85`, validated BDF `0000:8d:00.0`
- Immediate Barlow Ridge parent: `8086:5786`, validated BDF `0000:8c:00.0`
- Intel iGPU remains the display GPU
- RTX 2070 remains a secondary CUDA GPU

Validated kernel arguments:

```text
iommu=pt hpbussize=0x20 pcie_aspm=off pcie_ports=native pcie_port_pm=off thunderbolt.host_reset=false pci=realloc,assign-busses,resource_alignment=35@0000:8c:00.0
```

## Working solution

A signed kernel helper `tb5_gen3_pre`:

1. verifies the RTX 5090 and Barlow Ridge parent;
2. refuses to operate if the GPU is already driver-bound;
3. requires a naturally stable Gen4 x4 baseline;
4. sets Gen3 + Hardware Autonomous Speed Disable (HASD);
5. performs exactly one retrain before NVIDIA loads;
6. requires stable Gen3 x4, training clear, DLL active;
7. lets NVIDIA load;
8. reasserts Gen3/HASD without any further retrain.

Known-good states:

```text
0044 / 3044   natural Gen4 x4 before NVIDIA
0063 / 7043   stabilized Gen3 x4 + HASD
0061 / 7041   normal idle Gen1 x4 + HASD after NVIDIA
```

NVIDIA/PMU may still scale runtime link speed inside Gen1–Gen3 with GPU P-state. Idle Gen1 is not itself a failure.

## Validation

With the workaround:

- 4 KiB pageable CUDA: PASS
- 256 MiB pageable CUDA: PASS
- 4 KiB pinned allocation + CPU touch: PASS
- 4 KiB pinned H2D: PASS
- 4 KiB pinned D2H: PASS
- 1 MiB pinned bidirectional: PASS
- 64 MiB pinned bidirectional: PASS
- 128 MiB pinned bidirectional: PASS
- 256 MiB pinned bidirectional: PASS
- 20 consecutive 64 MiB pinned bidirectional cycles: PASS
- H2D ~3.05–3.07 GB/s
- D2H ~3.38 GB/s
- no Xid, Completion Timeout, Bad TLP, Bad DLLP, GPU loss, or host freeze in the validated final run

## Current engineering task

The working `.ko` was built manually for kernel `7.1.10-200.fc44.x86_64`.

Phase A packaging (specs, install/uninstall scripts, akmod notes) lives in `packaging/rpm/` and `docs/AKMOD_BUILD.md`. Do not install those RPMs until a later phase is approved. Start with `CURSOR_MASTER_PROMPT.md`.
