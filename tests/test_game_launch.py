"""The Windows game launch stays in the GUI and retains Forge diagnostics."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import standalone


class GameLaunchTests(unittest.TestCase):
    def test_windows_java_has_no_console_and_writes_log(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory)
            account = {"type": "local", "name": "Jugador", "id": "abc", "access_token": ""}
            with patch.object(standalone, "instance_game_dir", return_value=game), \
                 patch.object(standalone, "read_config", return_value={"memory_mb": 4096}), \
                 patch.object(standalone, "memory_limit_mb", return_value=8192), \
                 patch.object(standalone.mll.command, "get_minecraft_command", return_value=["java.exe", "-jar", "game.jar"]) as game_command, \
                 patch.object(standalone.sys, "platform", "win32"), \
                 patch.object(subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
                 patch.object(subprocess, "Popen") as launch:
                standalone.launch_game(account, game, "java.exe", "principal")
            launch.assert_called_once()
            args, kwargs = launch.call_args
            self.assertEqual(["java.exe", "-jar", "game.jar"], args[0])
            self.assertIn("-Djavax.net.ssl.trustStoreType=Windows-ROOT", game_command.call_args.args[2]["jvmArguments"])
            self.assertEqual(0x08000000, kwargs["creationflags"])
            self.assertEqual(subprocess.STDOUT, kwargs["stderr"])
            self.assertEqual(game / "logs" / "launcher-java.log", Path(kwargs["stdout"].name))
            self.assertTrue((game / "logs" / "launcher-java.log").is_file())


if __name__ == "__main__":
    unittest.main()
