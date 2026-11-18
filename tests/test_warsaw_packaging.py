from __future__ import annotations

import fnmatch
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def scriptlet(spec: str, name: str) -> str:
    """Body of a spec section, from its header line to the next section."""
    body: list[str] = []
    inside = False
    for line in spec.splitlines():
        if line.startswith("%") and line.split()[0] in SECTIONS:
            inside = line.split()[0] == name
            continue
        if inside:
            body.append(line)
    return "\n".join(body)


SECTIONS = {
    "%prep", "%build", "%install", "%check", "%pre", "%post", "%posttrans",
    "%preun", "%postun", "%files", "%changelog", "%description",
}


def params(service: ET.Element) -> dict[str, str]:
    return {item.get("name", ""): (item.text or "").strip() for item in service}


class WarsawPackagingTests(unittest.TestCase):
    def test_source_is_https_and_checksum_pinned(self):
        root = ET.parse(ROOT / "_service").getroot()
        services = root.findall("service")
        downloads = [item for item in services if item.get("name") == "download_url"]
        verifiers = [item for item in services if item.get("name") == "verify_file"]
        self.assertEqual(len(downloads), 1)
        self.assertEqual(len(verifiers), 1)

        download = params(downloads[0])
        self.assertEqual(download["protocol"], "https")
        self.assertEqual(download["host"], "cloud.gastecnologia.com.br")
        self.assertEqual(download["path"], "/bb/downloads/ws/warsaw_setup64.rpm")

        verify = params(verifiers[0])
        self.assertEqual(verify["file"], "_service:download_url:warsaw_setup64.rpm")
        self.assertEqual(verify["verifier"], "sha256")
        self.assertRegex(verify["checksum"], r"^[0-9a-f]{64}$")

    def test_spec_repackages_the_payload_without_modifying_it(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        self.assertRegex(spec, r"(?m)^Version:\s+2\.21\.4$")
        self.assertRegex(spec, r"(?m)^Release:\s+0$")
        self.assertRegex(spec, r"(?m)^Epoch:\s+1$")
        self.assertIn("LicenseRef-Warsaw-Redistributable", spec)
        self.assertIn("rpm2cpio", spec)
        self.assertIn("sha256sum --check --strict", spec)
        self.assertIn("__os_install_post %{nil}", spec)
        self.assertNotIn("%systemd_post", spec)

    def test_uses_opensuse_service_macros(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        self.assertIn("systemd-rpm-macros", spec)
        self.assertIn("%service_add_pre warsaw.service", scriptlet(spec, "%pre"))
        self.assertIn("%service_add_post warsaw.service", scriptlet(spec, "%post"))
        self.assertIn("%service_del_preun warsaw.service", scriptlet(spec, "%preun"))
        self.assertIn("%service_del_postun warsaw.service", scriptlet(spec, "%postun"))

    def test_owns_usr_local_etc_with_a_filter(self):
        # No openSUSE package owns /usr/local/etc and the OBS filelist check
        # rejects unowned directories, so the package owns it and filters
        # rpmlint's standard-dir-owned-by-package.
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        self.assertRegex(spec, r"(?m)^%dir /usr/local/etc$")
        rc = (ROOT / "warsaw-rpmlintrc").read_text(encoding="utf-8")
        self.assertIn('addFilter("standard-dir-owned-by-package /usr/local/etc")', rc)

    def test_rpmlint_filters_are_specific_and_documented(self):
        rc = (ROOT / "warsaw-rpmlintrc").read_text(encoding="utf-8")
        filters = [line for line in rc.splitlines() if line.startswith("addFilter(")]
        self.assertEqual(len(filters), 6)
        for line in filters:
            self.assertNotIn('"E: ', line)
            self.assertNotIn('"W: ', line)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for check in ("executable-stack", "missing-call-to-setgroups-before-setuid",
                      "filelist-forbidden-fhs23", "deprecated-init-script"):
            self.assertIn(check, readme)

    def test_license_files_are_one_per_line(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        for line in spec.splitlines():
            if line.startswith("%license"):
                self.assertEqual(len(line.split()), 2, line)

    def test_procps_replaces_procps_ng(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        requires = {
            line.split(":", 1)[1].strip()
            for line in spec.splitlines()
            if line.startswith("Requires:")
        }
        self.assertIn("procps", requires)
        self.assertNotIn("procps-ng", requires)

    def test_service_is_not_enabled_on_install(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        self.assertNotRegex(spec, r"systemctl\s+enable")
        self.assertIn("%service_del_preun warsaw.service", spec)
        preset = (ROOT / "warsaw.preset").read_text(encoding="utf-8")
        self.assertIn("disable warsaw.service", preset)

    def test_erase_stops_helpers_and_cleans_private_directories(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        preun = scriptlet(spec, "%preun")
        self.assertIn("for exe in /proc/[0-9]*/exe; do", preun)
        self.assertIn("/usr/local/bin/warsaw/*) pid=${exe#/proc/}; kill -9", preun)
        self.assertNotIn("pkill -9", spec)
        self.assertIn(
            "rm -rf /usr/local/bin/warsaw /usr/local/etc/warsaw /usr/local/lib/warsaw",
            spec,
        )

    def test_manifest_matches_the_packaged_payload(self):
        lines = (ROOT / "warsaw-files.sha256").read_text(encoding="utf-8").splitlines()
        entries: dict[str, str] = {}
        for line in lines:
            digest, path = line.split(maxsplit=1)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertFalse(path.startswith("/"), path)
            entries[path] = digest

        required = {
            "etc/init.d/warsaw",
            "usr/bin/warsaw",
            "usr/lib/systemd/system/warsaw.service",
            "usr/local/bin/warsaw/core",
            "usr/local/bin/warsaw/wsatspi",
            "usr/local/lib/warsaw/wsbrmu.so",
            "usr/share/licenses/warsaw/COPYING",
            "usr/share/licenses/warsaw/COPYING.LESSER",
        }
        self.assertTrue(required <= set(entries))
        self.assertEqual(len(entries), 28)

    def test_spec_files_cover_the_manifest(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        files = spec.split("%files", 1)[1].split("%changelog", 1)[0]
        files = files.replace("%{_datadir}", "/usr/share").replace("%{_prefix}", "/usr")
        patterns = [
            token
            for line in files.splitlines()
            for token in line.split()
            if token.startswith("/")
        ]
        for line in (ROOT / "warsaw-files.sha256").read_text(encoding="utf-8").splitlines():
            packaged = "/" + line.split(maxsplit=1)[1]
            self.assertTrue(
                any(fnmatch.fnmatchcase(packaged, pattern) for pattern in patterns),
                packaged,
            )

    def test_check_rejects_files_outside_the_manifest(self):
        check = scriptlet((ROOT / "warsaw.spec").read_text(encoding="utf-8"), "%check")
        self.assertIn("find . ! -type d", check)
        self.assertIn("! -path ./usr/lib/systemd/system-preset/90-warsaw.preset", check)
        self.assertIn("! -path ./usr/share/polkit-1/rules.d/50-warsaw.rules", check)
        self.assertIn("awk '{print $2}' %{SOURCE1} | LC_ALL=C sort | diff -u -", check)

    def test_core_finds_the_ca_bundle_at_the_red_hat_path(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        self.assertIn("Requires:       ca-certificates", spec)
        self.assertIn(
            "ln -s ../../../ssl/ca-bundle.pem %{buildroot}%{_sysconfdir}/pki/tls/certs/ca-bundle.crt",
            spec,
        )
        self.assertIn("%{_sysconfdir}/pki/tls/certs/ca-bundle.crt", scriptlet(spec, "%files"))
        self.assertIn("! -path ./etc/pki/tls/certs/ca-bundle.crt", scriptlet(spec, "%check"))

    def test_only_gas_dbd_is_configuration(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        configs = [line for line in spec.splitlines() if line.startswith("%config")]
        self.assertEqual(configs, ["%config(noreplace) /usr/local/etc/warsaw/gas.dbd"])
        self.assertNotIn("/usr/local/etc/warsaw/*", spec)

    def test_upgrade_from_vendor_rpm_disables_the_service(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        pre = scriptlet(spec, "%pre")
        post = scriptlet(spec, "%post")
        self.assertIn("rpm -q --qf '%%{EPOCH}\\n' warsaw", pre)
        self.assertIn("grep -qxF '(none)'", pre)
        self.assertNotIn("lyra", pre)
        self.assertIn("touch /run/warsaw-rpm-from-vendor", pre)
        self.assertIn("systemctl disable warsaw.service", post)
        self.assertNotIn("--now", post)

    def test_upgrade_stops_before_and_restarts_only_if_running(self):
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        pre = scriptlet(spec, "%pre")
        posttrans = scriptlet(spec, "%posttrans")
        self.assertIn("if [ $1 -ge 2 ]; then", pre)
        self.assertIn("systemctl is-active --quiet warsaw.service", pre)
        self.assertIn("touch /run/warsaw-rpm-restart", pre)
        self.assertIn("systemctl stop warsaw.service", pre)
        self.assertIn("for exe in /proc/[0-9]*/exe; do", pre)
        self.assertLess(pre.index("systemctl stop warsaw.service"), pre.index("for exe in /proc/"))
        self.assertIn("if [ -e /run/warsaw-rpm-restart ]; then", posttrans)
        self.assertIn("systemctl start warsaw.service", posttrans)


class NssdbLinkTests(unittest.TestCase):
    """warsaw-nssdb.sh: the CA must reach Chromium in new accounts (warsaw#22)."""

    def run_script(self, home: Path) -> subprocess.CompletedProcess:
        bindir = home.parent / "bin"
        bindir.mkdir(exist_ok=True)
        # Stand-in for certutil -N: records the call and creates the database.
        stub = bindir / "certutil"
        stub.write_text(
            '#!/bin/sh\n'
            'echo "$@" >> "$CERTUTIL_LOG"\n'
            'dir=${3#sql:}\n'
            ': > "$dir/cert9.db"\n',
            encoding="utf-8",
        )
        stub.chmod(0o755)
        env = {
            "HOME": str(home),
            "PATH": f"{bindir}:/usr/bin:/bin",
            "CERTUTIL_LOG": str(home.parent / "certutil.log"),
        }
        return subprocess.run(
            ["sh", str(ROOT / "warsaw-nssdb.sh")], env=env, capture_output=True, text=True
        )

    def test_new_account_gets_xdg_database_and_legacy_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            result = self.run_script(home)
            self.assertEqual(result.returncode, 0, result.stderr)
            xdg = home / ".local/share/pki/nssdb"
            legacy = home / ".pki/nssdb"
            self.assertTrue((xdg / "cert9.db").is_file())
            self.assertTrue(legacy.is_symlink())
            self.assertEqual(legacy.resolve(), xdg.resolve())
            self.assertEqual((home / ".pki").stat().st_mode & 0o777, 0o700)
            self.assertIn("--empty-password", (Path(tmp) / "certutil.log").read_text())

    def test_existing_xdg_database_is_linked_not_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = home / ".local/share/pki/nssdb"
            xdg.mkdir(parents=True)
            (xdg / "cert9.db").write_text("chromium", encoding="utf-8")
            self.assertEqual(self.run_script(home).returncode, 0)
            self.assertEqual((home / ".pki/nssdb").resolve(), xdg.resolve())
            self.assertEqual((xdg / "cert9.db").read_text(encoding="utf-8"), "chromium")
            self.assertFalse((Path(tmp) / "certutil.log").exists())

    def test_existing_legacy_database_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            legacy = home / ".pki/nssdb"
            legacy.mkdir(parents=True)
            self.assertEqual(self.run_script(home).returncode, 0)
            self.assertFalse(legacy.is_symlink())
            self.assertFalse((home / ".local/share/pki").exists())

    def test_broken_user_link_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            (home / ".pki").mkdir(parents=True)
            (home / ".pki/nssdb").symlink_to(home / "missing")
            self.assertEqual(self.run_script(home).returncode, 0)
            self.assertEqual(os.readlink(home / ".pki/nssdb"), str(home / "missing"))
            self.assertFalse((home / ".local/share/pki").exists())

    def test_user_unit_is_packaged_enabled_and_conditional(self):
        unit = (ROOT / "warsaw-nssdb.service").read_text(encoding="utf-8")
        self.assertIn("ConditionPathExists=!%h/.pki/nssdb", unit)
        self.assertIn("Type=oneshot", unit)
        self.assertIn("ExecStart=/usr/libexec/warsaw/warsaw-nssdb", unit)
        self.assertIn("WantedBy=default.target", unit)
        preset = (ROOT / "warsaw-user.preset").read_text(encoding="utf-8")
        self.assertIn("enable warsaw-nssdb.service", preset)
        spec = (ROOT / "warsaw.spec").read_text(encoding="utf-8")
        self.assertIn("Requires:       mozilla-nss-tools", spec)
        self.assertIn("%systemd_user_post warsaw-nssdb.service", scriptlet(spec, "%post"))
        self.assertIn("%systemd_user_preun warsaw-nssdb.service", scriptlet(spec, "%preun"))
        files = scriptlet(spec, "%files")
        for path in (
            "%{_libexecdir}/warsaw/warsaw-nssdb",
            "%{_userunitdir}/warsaw-nssdb.service",
            "%{_prefix}/lib/systemd/user-preset/90-warsaw.preset",
        ):
            self.assertIn(path, files)


if __name__ == "__main__":
    unittest.main()
