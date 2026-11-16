import tempfile
import unittest
from pathlib import Path

from watermedia_settings import remove_invalid_vlc_path


class WatermediaSettingsTests(unittest.TestCase):
    def test_invalid_path_removed_but_installed_vlc_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory)
            setting = game / "config/watermedia/custom_vlc_path.txt"
            setting.parent.mkdir(parents=True)
            setting.write_text(str(game / "absent"))
            remove_invalid_vlc_path(game)
            self.assertFalse(setting.exists())

            installed = game / "vlc"
            installed.mkdir()
            setting.write_text(str(installed))
            remove_invalid_vlc_path(game)
            self.assertEqual(setting.read_text(), str(installed))


if __name__ == "__main__":
    unittest.main()
