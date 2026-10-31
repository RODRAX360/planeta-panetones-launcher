"""One public launcher download stays at the same URL across builds."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import release_launcher
import release_launcher_linux


class StableReleaseTests(unittest.TestCase):
    def test_windows_manifest_uses_stable_asset_with_current_binary_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dist").mkdir()
            built = root / "dist/PlanetaPanetones-Setup-1.0.8.exe"
            built.write_bytes(b"installer for 1.0.8")
            base = "https://raw.githubusercontent.com/owner/repo/main"
            with patch.object(release_launcher, "ROOT", root), \
                    patch.object(release_launcher, "VERSION", "1.0.8"), \
                    patch.object(release_launcher, "read_config", return_value={
                        "launcher_update_url": base + "/launcher-update.json",
                    }), \
                    patch.object(sys, "argv", ["release_launcher.py", "--base-url", base]):
                release_launcher.main()

            stable = root / "dist/PlanetaPanetones-Setup.exe"
            manifest = json.loads((root / "dist/launcher-update.json").read_text(encoding="utf-8"))
            self.assertEqual(stable.read_bytes(), built.read_bytes())
            self.assertEqual(manifest["version"], "1.0.8")
            self.assertEqual(manifest["installer"], {
                "url": "https://github.com/RODRAX360/planeta-panetones-launcher/"
                       "releases/download/launcher/PlanetaPanetones-Setup.exe",
                "size": len(built.read_bytes()),
                "sha256": hashlib.sha256(built.read_bytes()).hexdigest(),
            })

    def test_linux_manifest_uses_stable_asset_and_keeps_executable_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dist").mkdir()
            built = root / "dist/PlanetaPanetones-1.0.8-x86_64.AppImage"
            built.write_bytes(b"AppImage for 1.0.8")
            built.chmod(0o755)
            with patch.object(release_launcher_linux, "ROOT", root), \
                    patch.object(release_launcher_linux, "VERSION", "1.0.8"):
                release_launcher_linux.main()

            stable = root / "dist/PlanetaPanetones-x86_64.AppImage"
            manifest = json.loads((root / "dist/launcher-update-linux.json").read_text(encoding="utf-8"))
            self.assertEqual(stable.read_bytes(), built.read_bytes())
            self.assertTrue(stable.stat().st_mode & 0o111)
            self.assertEqual(manifest["version"], "1.0.8")
            self.assertEqual(manifest["installer"], {
                "url": "https://github.com/RODRAX360/planeta-panetones-launcher/"
                       "releases/download/launcher/PlanetaPanetones-x86_64.AppImage",
                "size": len(built.read_bytes()),
                "sha256": hashlib.sha256(built.read_bytes()).hexdigest(),
            })


if __name__ == "__main__":
    unittest.main()
