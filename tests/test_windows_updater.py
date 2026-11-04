"""Validate the Windows update handoff before publishing an installer."""

import subprocess
import ssl
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import launcher_updates


class WindowsUpdaterTests(unittest.TestCase):
    def test_certificate_failure_has_actionable_message(self):
        error = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        message = launcher_updates.readable_error(error)
        self.assertIn("certificado HTTPS", message)
        self.assertNotIn("urlopen error", message)

    def test_failed_marker_rejects_invalid_version(self):
        with self.assertRaises(ValueError):
            launcher_updates.failed_update_marker("../../other")

    @unittest.skipUnless(sys.platform == "win32", "NSIS and cmd.exe are available on Windows")
    def test_handoff_reopens_launcher_after_install(self):
        with tempfile.TemporaryDirectory(prefix="planeta test ") as directory:
            root = Path(directory) / "ruta con espacios"
            root.mkdir()
            for name, marker in (("installer", "installed"), ("launcher", "launched")):
                source = root / f"{name}.nsi"
                executable = (root / "PlanetaPanetones-Setup-1.0.10.exe"
                              if name == "installer" else root / "launcher.exe")
                source.write_text(
                    'Unicode true\n'
                    'SilentInstall silent\n'
                    f'OutFile "{executable}"\n'
                    'Section\n'
                    f'  FileOpen $0 "$EXEDIR\\{marker}.txt" w\n'
                    f'  FileWrite $0 "{marker}"\n'
                    '  FileClose $0\n'
                    'SectionEnd\n',
                    encoding="utf-8",
                )
                subprocess.run(["makensis", "/NOCD", str(source)], check=True,
                               capture_output=True, timeout=20)
            with patch.object(launcher_updates, "data_dir", return_value=root), \
                    patch.object(launcher_updates.sys, "frozen", True, create=True), \
                    patch.object(launcher_updates.sys, "executable", str(root / "launcher.exe")), \
                    patch.object(launcher_updates.os, "getpid", return_value=999999):
                launcher_updates.start_installer_after_exit(root / "PlanetaPanetones-Setup-1.0.10.exe")
            deadline = time.monotonic() + 15
            while not (root / "launched.txt").is_file() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue((root / "installed.txt").is_file())
            self.assertTrue((root / "launched.txt").is_file())
            self.assertFalse((root / "updates/failed-1.0.10.txt").exists())


if __name__ == "__main__":
    unittest.main()
