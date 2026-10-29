"""Regression checks for the one-account policy and shared settings."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import standalone


class SingleIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.config = self.root / "launcher-config.json"
        self.config.write_text(json.dumps({"memory_mb": 4096, "manifest_url": ""}), encoding="utf-8")
        data_patch = patch.object(standalone, "data_dir", return_value=self.data)
        data_patch.start()
        self.addCleanup(data_patch.stop)
        config_patch = patch.object(standalone, "CONFIG_FILE", self.config)
        config_patch.start()
        self.addCleanup(config_patch.stop)

    def test_legacy_selection_is_only_usable_account_and_removal_does_not_reactivate_others(self):
        self.data.joinpath("accounts.json").write_text(json.dumps({"accounts": [
            {"id": "first", "name": "First", "refresh_token": "one"},
            {"id": "second", "name": "Second", "refresh_token": "two"},
        ]}), encoding="utf-8")
        self.data.joinpath("profiles.json").write_text(json.dumps({
            "selected": "local:Cuy", "local": [{"name": "Cuy"}, {"name": "Other"}],
        }), encoding="utf-8")

        state = standalone.game_state()
        self.assertEqual("Cuy", state["account"])
        self.assertEqual(["Cuy"], state["localProfiles"])
        self.assertEqual([], state["microsoftAccounts"])
        with self.assertRaisesRegex(ValueError, "Solo se permite una cuenta"):
            standalone.select_profile("microsoft:first")
        with self.assertRaisesRegex(ValueError, "Ya hay una cuenta guardada"):
            standalone.create_local_profile("NewCuy")

        standalone.remove_local_profile("Cuy")
        state = standalone.game_state()
        self.assertIsNone(state["account"])
        self.assertEqual([], state["localProfiles"])
        self.assertEqual([], state["microsoftAccounts"])
        self.assertEqual(2, len(json.loads(self.data.joinpath("accounts.json").read_text())["accounts"]))

        standalone.save_account({"id": "second", "name": "Second", "refresh_token": "new"})
        self.assertEqual("Second", standalone.game_state()["account"])
        with self.assertRaisesRegex(ValueError, "Ya hay una cuenta guardada"):
            standalone.save_account({"id": "first", "name": "First", "refresh_token": "new"})
        standalone.remove_microsoft_account("microsoft:second")
        self.assertIsNone(standalone.game_state()["account"])

    def test_local_profile_replacement_and_global_settings_are_shared(self):
        standalone.create_local_profile("Cuy")
        with self.assertRaisesRegex(ValueError, "Ya hay una cuenta guardada"):
            standalone.save_account({"id": "microsoft", "name": "Different"})
        standalone.remove_local_profile("Cuy")
        standalone.create_local_profile("Otro")
        self.assertEqual("Otro", standalone.game_state()["account"])

        standalone.set_instance("optimizada")
        standalone.save_global_settings(3072, 1280, 720, True)
        self.assertEqual(3072, standalone.read_config()["memory_mb"])
        self.assertEqual(1280, standalone.read_config()["resolution_width"])
        self.assertEqual("optimizada", standalone.selected_instance_id())
        before = self.data.joinpath("preferences.json").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "resolución"):
            standalone.save_global_settings(4096, 0, 720, True)
        self.assertEqual(before, self.data.joinpath("preferences.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
