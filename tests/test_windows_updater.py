"""Validate the Windows update handoff before publishing an installer."""

import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
