# Userspace integration for the TB5 RTX 5090 stabilizer.
# Does not provide tb5-egpu-gen3-kmod-common; that comes from the kmod SRPM.
# Scriptlets are inert: no systemctl preset/enable/disable/start/stop.

Name:           tb5-egpu-gen3
Version:        1.0.0
Release:        2%{?dist}
Summary:        Boot orchestration for the RTX 5090 Thunderbolt 5 Gen3 stabilizer
License:        GPL-2.0-only
URL:            https://github.com/ojoseph/fedora-tb5-nvidia-egpu-stabilizer

Source1:        egpu-gen3-preload.service
Source3:        egpu-gen3-kmod-start
Source4:        99-egpu-gen3-preload.modprobe.conf
Source5:        99-egpu-gen3-preload.dracut.conf
Source6:        README.md
Source7:        SAFETY_INVARIANTS.md
Source8:        TROUBLESHOOTING.md
Source9:        AKMOD_BUILD.md
Source10:       INVESTIGATION_LOG.md
Source11:       collect-support-bundle.sh
Source12:       smoke-readonly.sh
Source13:       cuda_pinned_bidir.py
Source14:       cuda_validation_harness.py

BuildArch:      noarch
BuildRequires:  systemd-rpm-macros

Requires:       akmod-tb5-egpu-gen3 >= %{version}
Requires:       systemd
Requires:       kmod
Requires:       %{_bindir}/nvidia-smi

%description
Systemd oneshot, modprobe NVIDIA blocker, and dracut omit rules that load
the signed tb5_gen3_pre helper before NVIDIA on the validated Thunderbolt 5
RTX 5090 path.

This package Requires akmod-tb5-egpu-gen3. It does not Provide
tb5-egpu-gen3-kmod-common; that common package is built from the kmod SRPM.

Install scriptlets do not preset, enable, disable, start, or stop
egpu-gen3-preload.service. Activation is an explicit administrator step
after helper signature and initramfs validation. Removing this RPM must
not operate on a hand-installed /etc unit of the same name.

%prep
%setup -q -T -c
cp -a %{SOURCE1} egpu-gen3-preload.service
cp -a %{SOURCE3} egpu-gen3-kmod-start
cp -a %{SOURCE4} 99-egpu-gen3-preload.modprobe.conf
cp -a %{SOURCE5} 99-egpu-gen3-preload.dracut.conf
cp -a %{SOURCE6} README.md
cp -a %{SOURCE7} SAFETY_INVARIANTS.md
cp -a %{SOURCE8} TROUBLESHOOTING.md
cp -a %{SOURCE9} AKMOD_BUILD.md
cp -a %{SOURCE10} INVESTIGATION_LOG.md
cp -a %{SOURCE11} collect-support-bundle.sh
cp -a %{SOURCE12} smoke-readonly.sh
cp -a %{SOURCE13} cuda_pinned_bidir.py
cp -a %{SOURCE14} cuda_validation_harness.py

%build
# No build. CUDA tests are never invoked.

%install
install -D -m 644 egpu-gen3-preload.service \
    %{buildroot}%{_unitdir}/egpu-gen3-preload.service
install -D -m 755 egpu-gen3-kmod-start \
    %{buildroot}%{_libexecdir}/%{name}/egpu-gen3-kmod-start
install -D -m 644 99-egpu-gen3-preload.modprobe.conf \
    %{buildroot}%{_modprobedir}/99-egpu-gen3-preload.conf
install -D -m 644 99-egpu-gen3-preload.dracut.conf \
    %{buildroot}%{_prefix}/lib/dracut/dracut.conf.d/99-egpu-gen3-preload.conf

install -D -m 755 collect-support-bundle.sh \
    %{buildroot}%{_libexecdir}/%{name}/collect-support-bundle.sh

# Manual diagnostics only. Mode 644 so they are not treated as boot helpers.
install -D -m 644 smoke-readonly.sh \
    %{buildroot}%{_datadir}/%{name}/tests/smoke-readonly.sh
install -D -m 644 cuda_pinned_bidir.py \
    %{buildroot}%{_datadir}/%{name}/tests/cuda_pinned_bidir.py
install -D -m 644 cuda_validation_harness.py \
    %{buildroot}%{_datadir}/%{name}/tests/cuda_validation_harness.py

# Intentionally no %%check and no scriptlet invocation of CUDA or PCIe retrain.

%post
echo "tb5-egpu-gen3: files installed. No systemctl preset/enable/start/stop."
echo "tb5-egpu-gen3: do not enable the unit until helper signature,"
echo "tb5-egpu-gen3: akmods build, and initramfs validation are complete."
echo "tb5-egpu-gen3: do not reboot yet. See AKMOD_BUILD.md."

%postun
if [ "$1" -eq 0 ]; then
    echo "tb5-egpu-gen3: package removed. RPM scriptlets did not disable or"
    echo "tb5-egpu-gen3: stop any service. Rebuild initramfs before reboot"
    echo "tb5-egpu-gen3: only after explicit migration. Do not retrain PCIe."
fi

%files
%dir %{_libexecdir}/%{name}
%dir %{_datadir}/%{name}
%dir %{_datadir}/%{name}/tests
%{_unitdir}/egpu-gen3-preload.service
%{_libexecdir}/%{name}/egpu-gen3-kmod-start
%{_libexecdir}/%{name}/collect-support-bundle.sh
%{_modprobedir}/99-egpu-gen3-preload.conf
%{_prefix}/lib/dracut/dracut.conf.d/99-egpu-gen3-preload.conf
%{_datadir}/%{name}/tests/smoke-readonly.sh
%{_datadir}/%{name}/tests/cuda_pinned_bidir.py
%{_datadir}/%{name}/tests/cuda_validation_harness.py
%doc README.md SAFETY_INVARIANTS.md TROUBLESHOOTING.md AKMOD_BUILD.md INVESTIGATION_LOG.md

%changelog
* Mon Sep 07 2026 Local maintainer <local@localhost> - 1.0.0-2
- Align integration RPM NVR with kmod 1.0.0-2. Scriptlets remain inert.

* Mon Sep 07 2026 Local maintainer <local@localhost> - 1.0.0-1
- Initial integration packaging: systemd, modprobe blocker, dracut omit, docs.
- Inert scriptlets: no systemctl preset/enable/disable/start/stop.
- Do not Provide tb5-egpu-gen3-kmod-common; that comes from the kmod SRPM.
