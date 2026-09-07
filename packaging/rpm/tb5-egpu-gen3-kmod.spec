# Local Fedora 44 akmod for the validated tb5_gen3_pre helper.
# Pattern: current kmodtool + buildforkernels akmod (same family as
# v4l2loopback-kmod). Do not require RPM Fusion koji kerneldevpkgs;
# akmods rebuilds against the installed kernel-devel on this machine.
#
# kmodtool --kmodname tb5-egpu-gen3-kmod strips the -kmod suffix, so:
#   akmod-tb5-egpu-gen3
#   kmod-tb5-egpu-gen3 (metapackage)
#   Requires: tb5-egpu-gen3-kmod-common
# This spec ships a payload-less tb5-egpu-gen3-kmod-common subpackage so
# the akmod can install without the integration RPM.
# The .ko filename remains tb5_gen3_pre.ko.

%if 0%{?fedora}
%global buildforkernels akmod
%endif
%global debug_package %{nil}
# Main NVRA has no payload. Source stays in Git and the SRPM; akmods rebuilds
# from /usr/src/akmods. kmodtool metapackages also use empty %%files.
%global _empty_manifest_terminate_build 0

Name:           tb5-egpu-gen3-kmod
Version:        1.0.0
Release:        2%{?dist}
Summary:        Kernel helper to stabilize an RTX 5090 Thunderbolt 5 link before NVIDIA
License:        GPL-2.0-only
URL:            https://github.com/ojoseph/fedora-tb5-nvidia-egpu-stabilizer
Source0:        %{name}-%{version}.tar.gz

ExclusiveArch:  x86_64

%global AkmodsBuildRequires %{_bindir}/kmodtool gcc make elfutils-libelf-devel
BuildRequires:  %{AkmodsBuildRequires}

# kmodtool generates akmod/kmod subpackages and %{akmod_install}.
%{expand:%(kmodtool --target %{_target_cpu} --kmodname %{name} %{?buildforkernels:--%{buildforkernels}} %{?kernels:--for-kernels "%{?kernels}"} 2>/dev/null) }

# kmodtool only emits akmod_install for the akmod SRPM build. akmods rebuilds
# pass --for-kernels, which must NOT stage /usr/src/akmods into BUILDROOT
# (that produces unpackaged-file errors). Only override when kernels is unset.
# Nested rpmbuild -bs also needs _topdir so it does not write ~/rpmbuild.
%if 0%{!?kernels:1}
%global akmod_install mkdir -p $RPM_BUILD_ROOT/%{_usrsrc}/akmods/; \\\
rpmbuild --define "_topdir %{_topdir}" \\\
--define "_sourcedir %{_sourcedir}" \\\
--define "_srcrpmdir $RPM_BUILD_ROOT/%{_usrsrc}/akmods/" \\\
%{?dist:--define "dist %{dist}"} \\\
-bs --nodeps %{_specdir}/%{name}.spec ; \\\
ln -s %{name}-%{version}-%{release}.src.rpm $RPM_BUILD_ROOT/%{_usrsrc}/akmods/%{pkg_kmod_name}.latest
%endif

# kmodtool Requires %%{pkg_kmod_name}-common. Ship it from this SRPM so
# akmod-tb5-egpu-gen3 does not depend on the integration RPM.
%package -n %{pkg_kmod_name}-common
Summary: Common dependency for tb5-egpu-gen3 kernel modules

%description -n %{pkg_kmod_name}-common
Payload-less common package required by kmodtool-generated akmod and kmod
packages. It contains no helper source, no boot orchestration, and no
systemd units. The integration package tb5-egpu-gen3 is optional and is
not required to install or rebuild this akmod.

%description
Out-of-tree kernel helper that establishes a Gen3 + HASD PCIe ceiling on
the validated Barlow Ridge to RTX 5090 path before NVIDIA binds. Runtime
module name is tb5_gen3_pre.

This package is the kmodtool source name. The installable payloads are
tb5-egpu-gen3-kmod-common, akmod-tb5-egpu-gen3 (SRPM under /usr/src/akmods),
and after akmods rebuilds, kmod-tb5-egpu-gen3-<kernel>. Helper source is
not installed under /usr/share.

%prep
%{?kmodtool_check}
kmodtool --target %{_target_cpu} --kmodname %{name} %{?buildforkernels:--%{buildforkernels}} %{?kernels:--for-kernels "%{?kernels}"} 2>/dev/null

%setup -q

for kernel_version in %{?kernel_versions} ; do
    mkdir -p _kmod_build_${kernel_version%%___*}
    cp -a Makefile tb5_gen3_pre.c _kmod_build_${kernel_version%%___*}/
done

%build
for kernel_version in %{?kernel_versions} ; do
    make %{?_smp_mflags} -C "${kernel_version##*___}" \
        M="${PWD}/_kmod_build_${kernel_version%%___*}" modules
done

%install
for kernel_version in %{?kernel_versions}; do
    install -d %{buildroot}%{?kmodinstdir_prefix}/${kernel_version%%___*}/%{?kmodinstdir_postfix}
    install -m 0755 _kmod_build_${kernel_version%%___*}/tb5_gen3_pre.ko \
        %{buildroot}%{?kmodinstdir_prefix}/${kernel_version%%___*}/%{?kmodinstdir_postfix}/
    chmod a+x %{buildroot}%{?kmodinstdir_prefix}/${kernel_version%%___*}/%{?kmodinstdir_postfix}/*.ko
done

%{?akmod_install}

# Intentionally no %%check: never compile, load, retrain, or run CUDA here.

# No files: helper source is not installed under /usr/share. The akmod
# subpackage owns /usr/src/akmods.
%files

%files -n %{pkg_kmod_name}-common

%changelog
* Mon Sep 07 2026 Local maintainer <local@localhost> - 1.0.0-2
- Do not run akmod_install during --for-kernels rebuilds.

* Mon Sep 07 2026 Local maintainer <local@localhost> - 1.0.0-1
- Initial akmod packaging of the validated hardcoded tb5_gen3_pre helper.
- Ship payload-less tb5-egpu-gen3-kmod-common from this SRPM.
