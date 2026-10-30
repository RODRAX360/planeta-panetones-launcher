"""Validate the Windows update handoff before publishing an installer."""

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import launcher_updates


class WindowsUpdaterTests(unittest.TestCase):
    def test_failed_marker_rejects_invalid_version(self):
        with self.assertRaises(ValueError):
            launcher_updates.failed_update_marker("../../other")

    @unittest.skipUnless(sys.platform == "win32", "PowerShell is available on Windows")
    def test_handoff_script_parses_in_powershell(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "handoff.ps1"
            script.write_text(launcher_updates.windows_handoff_script(), encoding="utf-8")
            escaped_path = str(script).replace("'", "''")
            command = (
                "$tokens = $null; $errors = $null; "
                f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped_path}', "
                "[ref]$tokens, [ref]$errors) > $null; "
                "if ($errors.Count -gt 0) { $errors | Write-Error; exit 1 }"
            )
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                           check=True, timeout=20)

    @unittest.skipUnless(sys.platform == "win32", "NSIS and PowerShell are available on Windows")
    def test_handoff_reopens_launcher_after_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, marker in (("installer", "installed"), ("launcher", "launched")):
                source = root / f"{name}.nsi"
                source.write_text(
                    'Unicode true\n'
                    'SilentInstall silent\n'
                    f'OutFile "{root / f"{name}.exe"}"\n'
                    'Section\n'
                    f'  FileOpen $0 "$EXEDIR\\{marker}.txt" w\n'
                    f'  FileWrite $0 "{marker}"\n'
                    '  FileClose $0\n'
                    'SectionEnd\n',
                    encoding="utf-8",
                )
                subprocess.run(["makensis", "/NOCD", str(source)], check=True,
                               capture_output=True, timeout=20)
            handoff = root / "handoff.ps1"
            handoff.write_text(launcher_updates.windows_handoff_script(), encoding="utf-8")
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", str(handoff), "999999", str(root / "installer.exe"),
                 str(root / "launcher.exe"), str(root / "ready.txt"),
                 str(root / "failed.txt"), str(root / "update.log")],
                check=True, timeout=30,
            )
            deadline = time.monotonic() + 5
            while not (root / "launched.txt").is_file() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue((root / "installed.txt").is_file())
            self.assertTrue((root / "launched.txt").is_file())
            self.assertFalse((root / "failed.txt").exists())


if __name__ == "__main__":
    unittest.main()
