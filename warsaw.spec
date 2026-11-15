Name:           warsaw
Version:        2.21.4
Release:        0
# OBS rewrites Release (lp161.N.M), which sorts below the vendor's "3".
# Epoch 1 makes this package supersede the unsigned vendor RPM of the same
# version; the vendor RPM has no Epoch.
Epoch:          1
Summary:        Warsaw security module for Brazilian internet banking
License:        LGPL-3.0-or-later AND LicenseRef-Warsaw-Redistributable
URL:            https://www.topaz.com.br/ofd/
Source0:        warsaw_setup64.rpm
Source1:        warsaw-files.sha256
Source2:        warsaw.preset
BuildRequires:  cpio
BuildRequires:  rpm
Requires:       python3
Requires:       procps
Requires:       zenity
ExclusiveArch:  x86_64

%global debug_package %{nil}
# Redistribute the official payload byte for byte. Every post-install brp
# script (strip, compress, shebang mangling, ...) could change the files and
# break the SHA-256 manifest verified in %check, so skip all of them.
%global __os_install_post %{nil}
# The .so files under /usr/local/lib/warsaw are private copies loaded by
# absolute path; do not advertise their generic SONAMEs as system Provides.
%global __provides_exclude_from ^/usr/local/lib/warsaw/.*$

%description
Warsaw (Topaz OFD, formerly GAS Tecnologia) is the security module required
by several Brazilian banks for internet banking. This package repackages the
official x86_64 RPM without recompiling or modifying its files. Only package
metadata differs: the obsolete procps-ng dependency is replaced by procps
(the openSUSE name), the package is signed by the Lyra OBS project key, and
warsaw.service is not enabled or started on install. The Vega "Bancos" card
enables the service only when the user asks.

The upstream installer at /usr/bin/warsaw can download components from the
manufacturer and write under /usr/local outside RPM ownership. Do not run it;
manage the packaged warsaw.service instead, so updates stay in Zypper.

%prep
%setup -q -c -T
mkdir payload
(cd payload && rpm2cpio %{SOURCE0} | cpio -idm --quiet --no-absolute-filenames)

%build
# The official RPM already contains the compiled payload; nothing is built.

%install
cp -a payload/. %{buildroot}/
install -D -m 0644 %{SOURCE2} %{buildroot}%{_prefix}/lib/systemd/system-preset/90-warsaw.preset

%check
# Every packaged file must match the official RPM byte for byte. This fails if
# anything in the build chain modified the binaries or libraries.
cd %{buildroot}
sha256sum --check --strict %{SOURCE1}
# The unit must stay off until the Vega card enables it.
grep -qxF 'disable warsaw.service' %{buildroot}%{_prefix}/lib/systemd/system-preset/90-warsaw.preset

%pre
# Drop markers left by an interrupted transaction.
rm -f /run/warsaw-rpm-from-vendor /run/warsaw-rpm-restart
if [ $1 -ge 2 ]; then
    # The vendor RPM enables warsaw.service in its %%post and its scriptlets
    # never disable it on upgrade. Remember that we are replacing it so %%post
    # can turn the boot-time activation off. The vendor RPM has no Epoch.
    if rpm -q --qf '%%{EPOCH}\n' warsaw 2>/dev/null | grep -qxF '(none)'; then
        touch /run/warsaw-rpm-from-vendor || :
    fi
    # Like the vendor %%pre, stop Warsaw before its files are replaced, so no
    # binary or library is swapped under a running process. %%posttrans starts
    # it again only if it was running.
    if systemctl is-active --quiet warsaw.service 2>/dev/null; then
        touch /run/warsaw-rpm-restart || :
    fi
    systemctl stop warsaw.service >/dev/null 2>&1 || :
    pkill -9 -f '^/usr/local/bin/warsaw/(core|sysdss|wsatspi|wsupdsl)( |$)' >/dev/null 2>&1 || :
fi

%post
# Do not enable, start or preset warsaw.service here: it runs as root and the
# user may install the package long before using a bank. The Vega "Bancos"
# card turns it on and off on demand.
systemctl daemon-reload >/dev/null 2>&1 || :
if [ -e /run/warsaw-rpm-from-vendor ]; then
    rm -f /run/warsaw-rpm-from-vendor
    systemctl disable warsaw.service >/dev/null 2>&1 || :
fi

%posttrans
if [ -e /run/warsaw-rpm-restart ]; then
    rm -f /run/warsaw-rpm-restart
    systemctl start warsaw.service >/dev/null 2>&1 || :
fi

%preun
if [ $1 -eq 0 ]; then
    systemctl --no-reload disable --now warsaw.service >/dev/null 2>&1 || :
    # Stopping the unit may leave wsatspi/sysdss helpers running; do not leave
    # processes behind after RPM removes their files.
    pkill -9 -f '^/usr/local/bin/warsaw/(core|sysdss|wsatspi|wsupdsl)( |$)' >/dev/null 2>&1 || :
fi

%postun
if [ $1 -eq 0 ]; then
    # Upstream writes runtime files under /usr/local outside RPM ownership;
    # the official postuninstall removes them with rm -rf. Do the same, scoped
    # to Warsaw's private directories, so an erase leaves nothing behind.
    rm -rf /usr/local/bin/warsaw /usr/local/etc/warsaw /usr/local/lib/warsaw >/dev/null 2>&1 || :
fi
systemctl daemon-reload >/dev/null 2>&1 || :

%files
%dir /usr/share/licenses/warsaw
%license %{_datadir}/licenses/warsaw/COPYING
%license %{_datadir}/licenses/warsaw/COPYING.LESSER
/etc/init.d/warsaw
/usr/bin/warsaw
%{_prefix}/lib/systemd/system/warsaw.service
%{_prefix}/lib/systemd/system-preset/90-warsaw.preset
%dir /usr/local/bin/warsaw
/usr/local/bin/warsaw/*
%dir /usr/local/etc
%dir /usr/local/etc/warsaw
# Same file flags as the vendor RPM: only gas.dbd is configuration. The other
# files are vendor data that must follow each upgrade.
%config(noreplace) /usr/local/etc/warsaw/gas.dbd
/usr/local/etc/warsaw/config.cfgc
/usr/local/etc/warsaw/features.datc
/usr/local/etc/warsaw/uninstall.dat
%dir /usr/local/lib/warsaw
/usr/local/lib/warsaw/*
%dir /usr/local/share/fonts
%dir /usr/local/share/fonts/truetype
/usr/local/share/fonts/truetype/dbldwrsw.ttf
/usr/share/locale/pt_BR/LC_MESSAGES/warsaw.mo
/usr/share/man/man1/warsaw.1.gz

%changelog
