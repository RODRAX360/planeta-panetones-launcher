import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from resource_pack import (
    ANIMATION_PACK_NAME,
    COMPATIBLE_PACK_NAME,
    PROFILE_PACK_ORDER,
    SETTINGS_PACK_NAME,
    _activate_packs,
    _write_compatible_pack,
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
            self.assertEqual(packs, ["mod/punchy:punchy", "vanilla", "mod_resources",
                                     "generated/fragmentum_layer", "file/Other.zip",
                                     "file/" + COMPATIBLE_PACK_NAME,
                                     "file/" + SETTINGS_PACK_NAME])

    def test_profile_packs_are_enabled_in_the_same_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary)
            folder = game / "resourcepacks"
            folder.mkdir()
            for item in PROFILE_PACK_ORDER:
                if item.startswith("file/"):
                    (folder / item[5:]).write_bytes(b"pack")
            options = game / "options.txt"
            options.write_text(
                'resourcePacks:["file/Icons v.1.14.zip","vanilla",'
                '"obscure_tooltips/packs/vibrant_tooltips",'
                '"file/§6Immersive_Interfaces_Modded.zip"]\n',
                encoding="utf-8",
            )
            _activate_packs(options)
            packs = json.loads(options.read_text().split("resourcePacks:", 1)[1])
            self.assertEqual(packs, [*PROFILE_PACK_ORDER,
                                     "file/" + COMPATIBLE_PACK_NAME,
                                     "file/" + SETTINGS_PACK_NAME])

    def test_local_compatibility_copy_keeps_animations_and_fixes_invalid_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / ANIMATION_PACK_NAME
            target = Path(temporary) / COMPATIBLE_PACK_NAME
            original = {
                "item_groups": {
                    "TRIDENT": {"animations": {"idle": {"animation": "trident_idle", "base_pose_retain": True}}},
                    "SHIELD": {"animations": {"use_item": {"animation": "shield_use", "base_pose_retain": True}}},
                },
                "defaults": {"animations": {"idle_events": {"variants": []}}},
            }
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("pack.mcmeta", "{}")
                archive.writestr("assets/punchy_moves/compat/develop.json", json.dumps(original))
                archive.writestr("assets/punchy_moves/animations/keep.json", "{}")
            _write_compatible_pack(source, target)
            with zipfile.ZipFile(target) as archive:
                data = json.loads(archive.read("assets/punchy_moves/compat/develop.json"))
                self.assertIn("assets/punchy_moves/animations/keep.json", archive.namelist())
                self.assertEqual(data["item_groups"]["TRIDENT"]["animations"]["idle"],
                                 {"animation": "trident_idle"})
                self.assertEqual(data["item_groups"]["SHIELD"]["animations"]["use_item"],
                                 {"animation": "shield_use"})
                self.assertTrue(data["defaults"]["animations"]["idle_events"]["variants"])
            with zipfile.ZipFile(source) as archive:
                self.assertEqual(json.loads(archive.read("assets/punchy_moves/compat/develop.json")), original)

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
