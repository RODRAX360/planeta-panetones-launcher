"""Linux AppImage releases use their own update feed and writable executable."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher_updates
import standalone


class LinuxReleaseTests(unittest.TestCase):
    def test_linux_reads_its_own_update_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "launcher-config.json"
            config.write_text(json.dumps({
                "manifest_url": "https://example.org/pack/manifest.json",
                "launcher_update_url": "https://example.org/pack/launcher-update.json",
                "memory_mb": 4096,
            }), encoding="utf-8")
            with patch.object(standalone, "CONFIG_FILE", config), patch.object(standalone.sys, "platform", "linux"), \
                    patch.object(standalone, "data_dir", return_value=root):
                self.assertEqual(standalone.read_config()["launcher_update_url"],
                                 "https://example.org/pack/launcher-update-linux.json")

    def test_linux_self_update_requires_writable_appimage(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "launcher.AppImage"
            image.write_bytes(b"appimage")
            with patch.object(launcher_updates.sys, "platform", "linux"), \
                    patch.object(launcher_updates.sys, "frozen", True, create=True), \
                    patch.dict(launcher_updates.os.environ, {"APPIMAGE": str(image)}):
                self.assertTrue(launcher_updates.can_self_update())
                image.unlink()
                self.assertFalse(launcher_updates.can_self_update())


if __name__ == "__main__":
    unittest.main()
