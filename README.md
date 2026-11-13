# Warsaw packaging

RPM packaging of the official Warsaw x86_64 security module (Topaz OFD,
formerly GAS Tecnologia / Diebold Nixdorf), required by several Brazilian banks
for internet banking. It is repackaged for the signed Lyra OS OBS
repositories.

This repository contains packaging metadata only; Warsaw is not
Lyra-authored code. The payload is redistributed byte for byte.

| File | Purpose |
| --- | --- |
| `_service` | OBS source service: downloads the official RPM over HTTPS and verifies its SHA-256 |
| `warsaw.spec` | Extracts the official RPM with `rpm2cpio` and installs the same files at the same paths, without compiling or modifying them |
| `warsaw-files.sha256` | Pinned SHA-256 of every packaged file, checked in `%check` |
| `warsaw.preset` | Keeps `warsaw.service` disabled, so systemd presets do not enable it at install or first boot |
| `warsaw.changes` | openSUSE-style RPM changelog |

## What differs from the official RPM

Only metadata changes; every binary, library, configuration and data file is
byte-for-byte identical to `warsaw_setup64.rpm` 2.21.4-3:

- `Requires: procps` replaces the original `procps-ng`, which does not exist on
  openSUSE (the package is named `procps`);
- the RPM is signed by the Lyra OBS project key, and its release is `3.lyra1`
  so it supersedes the unsigned vendor `2.21.4-3` if one is already installed;
- `%post` does not enable or start `warsaw.service`. The Vega "Bancos" card
  enables and disables it only when the user asks, and `%preun` stops and
  disables it on erase;
- on erase, `%preun` also kills leftover `core`/`wsatspi` helpers and
  `%postun` removes Warsaw's private directories under `/usr/local`, as the
  official `postuninstall` does, so nothing survives the package;
- `90-warsaw.preset` disables the unit for `systemctl preset` and first boot.

The official RPM ships no signature, so the chain of trust is the pinned
SHA-256 in `_service` plus the OBS project signature.

Topaz publishes the same payload for Banco do Brasil
(`bb/downloads/ws/warsaw_setup64.rpm`) and Caixa
(`cef/warsaw/install/GBPCEFwr64.rpm`); both mirrors are byte-identical and
share the pinned SHA-256. The daily `upstream-versions` check in
`lyra-ecosystem` downloads both and reports when either changes, including its
`Last-Modified`.

## Upstream installer and updater

The payload ships two entry points that matter for updates:

- `/usr/local/bin/warsaw/wsupdsl` is **not** a self-updater. It is a restart
  watchdog for `warsaw.service`: it only restarts the service if `core` died.
- `/usr/bin/warsaw` is the upstream installer. `warsaw start` can download
  components from the manufacturer over HTTP and write under `/usr/local`,
  outside RPM ownership.

Do not run the upstream installer. Manage the packaged `warsaw.service`
instead, so installed files stay owned by RPM and updates arrive only through
Zypper and the signed Lyra repositories. If upstream ever starts updating
`core` by itself, that behavior must be documented and gated; it is not
expected today.

The package installs `/etc/init.d/warsaw` because it is part of the official
payload, but systemd uses `/usr/lib/systemd/system/warsaw.service`
(`Type=forking`, `ExecStart=/usr/local/bin/warsaw/core`,
`PIDFile=/var/run/core.pid`, `Restart=always`). The Vega card must use
`systemctl` directly, never `warsaw start`.

## License status

The official RPM declares `License: Redistributable, no modification
permitted`, while the Warsaw Installer and the packaged license files are
LGPL-3.0-or-later. This package redistributes the exact binaries and libraries
without modifying them and only adjusts RPM metadata; the working
interpretation is that this is redistribution, not modification.

A written confirmation from Topaz must be kept before the package is promoted
to the release repository. If the manufacturer does not accept this
interpretation, the package must not be redistributed and the Vega card must
use the guided download path (vega#208/#263) instead. Until then, treat the
package as staging-only.

The upstream license files are installed at `/usr/share/licenses/warsaw/`.

## Build and validation

CI runs on every push to `main` and pull request:

```sh
python3 -m unittest discover -s tests -v
rpmspec -P warsaw.spec >/dev/null
```

The tests require HTTPS plus a pinned SHA-256 for the upstream RPM, the
`procps` requirement, no automatic service enablement, the disabling preset,
and a manifest that matches the payload. The OBS build runs
`sha256sum --check --strict` on every packaged file after `%install`; a
stripped or otherwise modified file fails the build. `__os_install_post` is
disabled so no `brp-*` script touches the payload.

Qualification on a clean Leap 16.1 VM still has to prove:

- install, upgrade and erase leave no orphan file under `/usr/local`;
- `warsaw.service` starts only when enabled, works with SELinux enforcing and
  leaves no unexpected listener or process after being stopped;
- the Vega "Bancos" card can enable, check and disable the service through the
  existing D-Bus contract (`Services.SetServiceEnabled` and
  `Services.SetServiceRunning`), without calling the upstream installer.

## Updating

When Topaz publishes a new RPM:

1. replace the SHA-256 in `_service` and regenerate the download;
2. update `warsaw-files.sha256` from the new payload;
3. bump `Version`/`Release`, add a `warsaw.changes` entry and update
   `upstream-versions.toml` in `lyra-ecosystem` (both mirror URLs);
4. build in the OBS staging project, qualify on Leap 16.1 and only then
   promote.

## Credits

Warsaw is developed by Topaz OFD (formerly GAS Tecnologia / Diebold Nixdorf).
See <https://www.topaz.com.br/ofd/>. The upstream license files are distributed
with the official RPM.
