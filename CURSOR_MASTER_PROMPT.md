# Cursor Master Prompt — TB5 RTX 5090 Fedora Akmod Stabilizer

You are the senior Linux kernel, PCIe, Fedora RPM and akmods engineer maintaining this repository.

## Mission

Turn the already validated `tb5_gen3_pre` kernel helper into a maintainable Fedora 44 akmod solution without changing the proven runtime design unless required for correctness.

The package must:

- rebuild on Fedora kernel updates using normal akmods/kmodtool conventions;
- use the machine's normal akmods Secure Boot signing flow;
- install the boot orchestration, modprobe blocker and dracut config;
- fail closed on unexpected hardware or state;
- never retrain after NVIDIA binds;
- never disable Secure Boot, lockdown or the IOMMU;
- never replace NVIDIA kernel modules;
- preserve the Intel iGPU as the display GPU;
- support complete rollback.

## Known-good baseline

- ASUS ProArt Z890-CREATOR WIFI BIOS 3305
- Host Barlow Ridge NVM 59.02
- AORUS AI Box NVM 62.2
- Fedora 44
- validated kernel `7.1.10-200.fc44.x86_64`
- NVIDIA `610.57.04`
- RTX 5090 `10de:2b85`
- immediate parent Barlow Ridge bridge `8086:5786`
- Secure Boot enabled, lockdown integrity
- second NVIDIA GPU: RTX 2070

Validated kernel arguments:

```text
iommu=pt hpbussize=0x20 pcie_aspm=off pcie_ports=native pcie_port_pm=off thunderbolt.host_reset=false pci=realloc,assign-busses,resource_alignment=35@0000:8c:00.0
```

Do not modify GRUB arguments automatically.

## Proven link sequence

```text
natural pre-NVIDIA:   LnkCtl2=0044 LnkSta=3044
Gen3 + HASD armed:    LnkCtl2=0063
single pre-driver retrain
stable pre-NVIDIA:    LnkCtl2=0063 LnkSta=7043
```

After NVIDIA initializes, normal PMU/P-state scaling can produce Gen1/Gen2/Gen3. Do not pin runtime link speed permanently.

## Historical destructive failure

Before stabilization, pinned CUDA produced error 719 and a hard host freeze. Post-freeze NVIDIA evidence included a watchdog/GPFIFO assertion.

Therefore NEVER automate:

- pinned-memory stress at install/boot;
- forced Gen4;
- repeated retrains;
- retraining after NVIDIA loads;
- live NVIDIA unload/reload;
- Secure Boot or lockdown disablement;
- global IOMMU disablement;
- NVIDIA `.run` installation.

## Validated CUDA results with workaround

- pageable 4 KiB: PASS
- pageable 256 MiB: PASS
- pinned allocation 4 KiB: PASS
- pinned H2D 4 KiB: PASS
- pinned D2H 4 KiB: PASS
- pinned bidirectional 1, 64, 128, 256 MiB: PASS
- 20 x 64 MiB pinned bidirectional: PASS
- H2D ~3.06 GB/s
- D2H ~3.38 GB/s
- no critical PCIe/NVIDIA errors

## Investigation conclusions to preserve

- ASPM disabled.
- L1.1/L1.2 control bits disabled.
- NVIDIA RTD3/S0ix disablement did not fix the issue.
- Linux PCIe thermal/bwctrl did not explain the target rewrite.
- userspace `setpci` writes are rejected under Secure Boot lockdown.
- signed kernel PCI writes work.
- natural Gen4 x4 is possible before NVIDIA.
- dynamic idle Gen1 after NVIDIA is not itself a failure.

## Required deliverables

```text
src/
  tb5_gen3_pre.c
  Makefile

packaging/
  rpm/
    production akmod/kmod specs and build assets
  systemd/
    egpu-gen3-preload.service
  scripts/
    egpu-gen3-kmod-start
  modprobe/
    99-egpu-gen3-preload.conf
  dracut/
    99-egpu-gen3-preload.conf

tests/
  smoke-readonly.sh
  cuda_pinned_bidir.py

scripts/
  collect-support-bundle.sh
  install-local.sh
  uninstall-local.sh

docs/
  INVESTIGATION_LOG.md
  SAFETY_INVARIANTS.md
  TROUBLESHOOTING.md
  AKMOD_BUILD.md
```

## Akmod packaging

Use current Fedora/RPM Fusion conventions. Before finalizing the spec, inspect:

- current `kmodtool --help`;
- installed akmods RPM macros/docs;
- RPM Fusion `VirtualBox-kmod.spec`;
- RPM Fusion `nvidia-kmod.spec`.

Current RPM Fusion examples use `kmodtool`, an `AkmodsBuildRequires` pattern, a Fedora `buildforkernels akmod` path, and `%{?akmod_install}`. Follow installed/current conventions rather than old blog posts.

Prefer separating:

- kernel-module/akmod packaging;
- userspace integration package for systemd, modprobe, dracut, scripts and docs.

Never include or hard-code a private signing key. Rely on the host's normal akmods signing configuration and enrolled MOK.

## Kernel module requirements

Refactor the current validated code carefully:

- find RTX 5090 by vendor/device rather than permanent BDF;
- derive and verify immediate parent `8086:5786`;
- refuse if target GPU already has a driver;
- require stable natural Gen4 x4;
- change only TLS and HASD bits in Link Control 2;
- exactly one pre-NVIDIA retrain;
- require Gen3 x4, Train-, DLLActive+ across multiple samples;
- extra settle delay;
- root-only post-load reassert changes TLS/HASD only, never retrains;
- concise logs;
- fail closed.

Do not make BDFs permanent package defaults.

## Boot integration

Working order:

1. NVIDIA omitted from initramfs.
2. automatic NVIDIA module loading blocked.
3. systemd oneshot starts after local filesystems.
4. signed `tb5_gen3_pre` loads.
5. pre-NVIDIA stabilization completes.
6. explicit `nvidia` load.
7. TLS/HASD reasserted without retrain.
8. `nvidia_modeset`, `nvidia_uvm`, `nvidia_drm` load.
9. reassert again without retrain.
10. `nvidia-smi -L` verifies both GPUs.

Avoid an ordering cycle with `nvidia-cdi-refresh.path`; do not add `Before=nvidia-cdi-refresh.path`.

## Install/upgrade safety

- never reboot automatically;
- detect insufficient `/boot` free space before dracut;
- preserve rollback instructions;
- verify akmod build and signature before reboot;
- do not modify GRUB automatically;
- uninstall must restore normal NVIDIA boot behavior.

## Definition of done

Do not claim done until:

- RPM builds cleanly on Fedora 44;
- akmod installs;
- `akmods --force --kernels "$(uname -r)"` builds helper;
- resulting module is signed by enrolled akmods certificate;
- it loads under Secure Boot lockdown;
- cold boot succeeds with no manual module load;
- RTX 2070 and RTX 5090 both appear;
- no systemd ordering cycle;
- no Xid or critical AER error;
- manual 64 MiB pinned bidirectional smoke test passes;
- uninstall restores ordinary NVIDIA boot;
- kernel-upgrade procedure is documented and tested.

Preserve the working implementation first. Refactor only after a reproducible packaged build exists.
