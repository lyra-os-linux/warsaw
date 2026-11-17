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
Source3:        warsaw.rules
BuildRequires:  cpio
BuildRequires:  rpm
BuildRequires:  systemd-rpm-macros
Requires:       python3
Requires:       polkit
Requires:       procps
Requires:       zenity
ExclusiveArch:  x86_64
%{?systemd_ordering}

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
# Lets the active local session start and stop only warsaw.service, for the
# Vega bank web apps (vega#210).
install -D -m 0644 %{SOURCE3} %{buildroot}%{_datadir}/polkit-1/rules.d/50-warsaw.rules

%check
# Every packaged file must match the official RPM byte for byte. This fails if
# anything in the build chain modified the binaries or libraries.
cd %{buildroot}
sha256sum --check --strict %{SOURCE1}
# The manifest must also list every packaged file: a file added by a new
# vendor RPM would otherwise ship without a hash check (warsaw#3). Only the
# two files Lyra adds (preset and polkit rule) are outside the manifest.
find . ! -type d \
    ! -path ./usr/lib/systemd/system-preset/90-warsaw.preset \
    ! -path ./usr/share/polkit-1/rules.d/50-warsaw.rules \
    -printf '%%P\n' | LC_ALL=C sort > %{_builddir}/payload.list
awk '{print $2}' %{SOURCE1} | LC_ALL=C sort | diff -u - %{_builddir}/payload.list
# The unit must stay off until the Vega card enables it.
grep -qxF 'disable warsaw.service' %{buildroot}%{_prefix}/lib/systemd/system-preset/90-warsaw.preset

%pre
%service_add_pre warsaw.service
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
    # Match the executable, not the command line: a helper started with
    # another argv[0] would escape a pkill -f pattern (warsaw#2).
    for exe in /proc/[0-9]*/exe; do
        case $(readlink "$exe" 2>/dev/null) in
            /usr/local/bin/warsaw/*) pid=${exe#/proc/}; kill -9 "${pid%%/exe}" >/dev/null 2>&1 || : ;;
        esac
    done
fi

%post
# Do not enable or start warsaw.service here: it runs as root and the user may
# install the package long before using a bank. The Vega "Bancos" card turns
# it on and off on demand. On a fresh install %%service_add_post applies
# 90-warsaw.preset, which keeps the unit disabled.
%service_add_post warsaw.service
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
# Stops and disables warsaw.service on erase.
%service_del_preun warsaw.service
if [ $1 -eq 0 ]; then
    # Stopping the unit may leave wsatspi/sysdss helpers running; do not leave
    # processes behind after RPM removes their files.
    # Match the executable, not the command line: a helper started with
    # another argv[0] would escape a pkill -f pattern (warsaw#2).
    for exe in /proc/[0-9]*/exe; do
        case $(readlink "$exe" 2>/dev/null) in
            /usr/local/bin/warsaw/*) pid=${exe#/proc/}; kill -9 "${pid%%/exe}" >/dev/null 2>&1 || : ;;
        esac
    done
fi

%postun
if [ $1 -eq 0 ]; then
    # Upstream writes runtime files under /usr/local outside RPM ownership;
    # the official postuninstall removes them with rm -rf. Do the same, scoped
    # to Warsaw's private directories, so an erase leaves nothing behind.
    rm -rf /usr/local/bin/warsaw /usr/local/etc/warsaw /usr/local/lib/warsaw >/dev/null 2>&1 || :
fi
%service_del_postun warsaw.service

%files
%dir /usr/share/licenses/warsaw
%license %{_datadir}/licenses/warsaw/COPYING
%license %{_datadir}/licenses/warsaw/COPYING.LESSER
/etc/init.d/warsaw
/usr/bin/warsaw
%{_prefix}/lib/systemd/system/warsaw.service
%{_prefix}/lib/systemd/system-preset/90-warsaw.preset
%{_datadir}/polkit-1/rules.d/50-warsaw.rules
%dir /usr/local/bin/warsaw
/usr/local/bin/warsaw/*
# Nothing in openSUSE owns /usr/local/etc; the OBS filelist check fails if
# this package does not.
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
