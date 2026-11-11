import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from profile_options import TEMPLATE, apply_profile_options
from publish_pack import (SKIN_COREMOD_NEW, SKIN_COREMOD_OLD,
                          SKIN_MOD_NAME, copy_extra_mods)


class ProfileOptionsTests(unittest.TestCase):
    def test_applies_language_keys_once_and_keeps_unrelated_user_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary)
            template = game / TEMPLATE
            template.parent.mkdir(parents=True)
            template.write_text("lang:es_mx\nkey_key.jump:key.keyboard.space\n", encoding="utf-8")
            options = game / "options.txt"
            options.write_text("lang:en_us\nkey_key.jei.showRecipe:key.keyboard.r\nfov:0.7\n")
            apply_profile_options(game)
            self.assertEqual(options.read_text(),
                             "lang:es_mx\nfov:0.7\nkey_key.jump:key.keyboard.space\n")
            options.write_text(options.read_text().replace("lang:es_mx", "lang:es_es"))
            apply_profile_options(game)
            self.assertIn("lang:es_es", options.read_text())

    def test_custom_skin_loader_keeps_mod_and_skips_only_cape_transform(self):
        with tempfile.TemporaryDirectory() as temporary:
            from unittest.mock import patch
            root = Path(temporary)
            bundled = root / "bundled"
            bundled.mkdir()
            with zipfile.ZipFile(bundled / SKIN_MOD_NAME, "w") as archive:
                archive.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\r\n\r\nName: transformers.js\r\nSHA-256-Digest: old\r\n\r\n")
                archive.writestr("META-INF/CUSTOMSK.SF", b"signature")
                archive.writestr("transformers.js", SKIN_COREMOD_OLD)
                archive.writestr("keep.class", b"skin loader")
            with patch("publish_pack.EXTRA_MODS", bundled):
                entries = copy_extra_mods(root / "files")
            self.assertEqual(len(entries), 1)
            self.assertIn("PlanetaCompat.jar", entries[0]["path"])
            with zipfile.ZipFile(root / "files" / entries[0]["path"]) as archive:
                self.assertEqual(archive.read("transformers.js").decode(), SKIN_COREMOD_NEW)
                self.assertEqual(archive.read("keep.class"), b"skin loader")
                self.assertEqual(archive.read("META-INF/MANIFEST.MF"), b"Manifest-Version: 1.0\r\n\r\n")
                self.assertNotIn("META-INF/CUSTOMSK.SF", archive.namelist())


if __name__ == "__main__":
    unittest.main()
