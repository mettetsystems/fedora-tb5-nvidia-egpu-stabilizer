# Akmod Packaging Plan

Use a current RPM Fusion-style akmod design rather than a custom updater.

Current reference implementations:
- https://github.com/rpmfusion/VirtualBox-kmod/blob/master/VirtualBox-kmod.spec
- https://github.com/rpmfusion/nvidia-kmod/blob/master/nvidia-kmod.spec

Current RPM Fusion specs demonstrate `kmodtool`, `AkmodsBuildRequires`, Fedora `buildforkernels akmod`, and `%{?akmod_install}` patterns.

Recommended split:
- `tb5-egpu-gen3-kmod` source/kmod/akmod packaging, including payload-less `tb5-egpu-gen3-kmod-common`
- `tb5-egpu-gen3` integration RPM containing systemd, modprobe, dracut, scripts and docs
  (Requires akmod; does not Provide the kmodtool common name)

Do not ship a private signing key. Let normal akmods signing use the host's configured/enrolled key.

Production specs for this split are:

- `packaging/rpm/tb5-egpu-gen3-kmod.spec`
- `packaging/rpm/tb5-egpu-gen3.spec`

Build steps: `docs/AKMOD_BUILD.md`. Do not install, rebuild initramfs, or reboot from the spec files.

Before finalizing the spec, inspect the versions of `akmods`, `kmodtool` and RPM macros actually installed on Fedora 44.
