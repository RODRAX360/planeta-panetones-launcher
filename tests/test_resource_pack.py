import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from resource_pack import (
    ANIMATION_PACK_NAME,
    SETTINGS_PACK_NAME,
    _activate_packs,
    _write_settings_pack,
)


class ResourcePackTests(unittest.TestCase):
    def test_activation_preserves_other_options_and_replaces_old_pack(self):
        with tempfile.TemporaryDirectory() as temporary:
            options = Path(temporary) / "options.txt"
            options.write_text(
                'fov:0.5\nresourcePacks:["vanilla","file/Other.zip",'
                '"file/Fluid & Foolish 1.0-hotfix.zip"]\nsoundCategory_master:0.8\n',
                encoding="utf-8",
            )
            _activate_packs(options)
            once = options.read_text(encoding="utf-8")
            _activate_packs(options)
            self.assertEqual(once, options.read_text(encoding="utf-8"))
            self.assertIn("fov:0.5\n", once)
            self.assertIn("soundCategory_master:0.8\n", once)
            packs = json.loads(next(line.partition(":")[2] for line in once.splitlines()
                                    if line.startswith("resourcePacks:")))
            self.assertEqual(packs, ["vanilla", "file/Other.zip",
                                     "file/" + ANIMATION_PACK_NAME,
                                     "file/" + SETTINGS_PACK_NAME])

    def test_settings_pack_disables_only_random_idle_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / SETTINGS_PACK_NAME
            _write_settings_pack(destination)
            with zipfile.ZipFile(destination) as archive:
                settings = json.loads(archive.read(
                    "assets/punchy_moves/compat/zz_planeta_idle.json"))
                self.assertEqual(settings["defaults"]["animations"]["idle_events"]["chance"], 0)
                self.assertEqual(set(settings["defaults"]["animations"]), {"idle_events"})


if __name__ == "__main__":
    unittest.main()
