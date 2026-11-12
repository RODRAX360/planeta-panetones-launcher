"""A damaged Java runtime must not be repaired over DLLs in use on Windows."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import minecraft_launcher_lib as mll

import standalone


class JavaRuntimeTests(unittest.TestCase):
    def test_installs_beside_locked_runtime_and_reuses_completed_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            game = data / "minecraft"
            game.mkdir()
            name = "java-runtime-gamma"
            old_java = str(game / "runtime" / name / "bin" / "java.exe")

            def executable(_name, root):
                if Path(root) == game:
                    return old_java
                return str(Path(root) / "runtime" / name / "bin" / "java.exe")

            def install(_name, root, callback):
                self.assertNotEqual(Path(root), game)
                Path(executable(name, root)).parent.mkdir(parents=True)
                Path(executable(name, root)).touch()

            with patch.object(standalone, "data_dir", return_value=data), \
                 patch.object(mll.runtime, "get_executable_path", side_effect=executable), \
                 patch.object(mll.runtime, "install_jvm_runtime", side_effect=install) as installer, \
                 patch.object(standalone, "_usable_java", side_effect=lambda path: path != old_java):
                runtime = {"javaMajorVersion": 17}
                first = standalone._get_or_install_java(name, game, runtime, {}, lambda _text: None)
                second = standalone._get_or_install_java(name, game, runtime, {}, lambda _text: None)

            self.assertEqual(first, second)
            self.assertEqual(installer.call_count, 1)
            self.assertTrue((Path(first).parents[3] / ".ready").is_file())


if __name__ == "__main__":
    unittest.main()
