import json
import tempfile
import unittest
from pathlib import Path

from diorama_settings import initialize_diorama


class DioramaSettingsTests(unittest.TestCase):
    def test_minimap_starts_hidden_without_resetting_player_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory)
            initialize_diorama(game)
            config = game / "diorama/config.json"
            self.assertFalse(json.loads(config.read_text())["minimap"])
            config.write_text('{"minimap": true, "minimapSize": 128}')
            initialize_diorama(game)
            self.assertEqual(json.loads(config.read_text()),
                             {"minimap": True, "minimapSize": 128})


if __name__ == "__main__":
    unittest.main()
