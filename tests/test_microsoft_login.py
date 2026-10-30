"""Microsoft sign-in regression checks without contacting Microsoft services."""

import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

import minecraft_launcher_lib as mll

import standalone


class CallbackServer:
    def __init__(self, _address, _handler):
        self.callback_url = None
        self.timeout = None

    def handle_request(self):
        self.callback_url = "http://localhost:8765/callback?code=ok&state=expected"

    def server_close(self):
        pass


class MicrosoftLoginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        data = root / "data"
        data.mkdir()
        config = root / "launcher-config.json"
        config.write_text(json.dumps({
            "microsoft_client_id": "test-client",
            "redirect_uri": "http://localhost:8765/callback",
            "memory_mb": 4096,
        }), encoding="utf-8")
        for target, value in (("data_dir", data), ("CONFIG_FILE", config)):
            patcher = patch.object(standalone, target, return_value=value) if target == "data_dir" else patch.object(standalone, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _login(self, *, fresh=False, complete_login=None):
        account = {"id": "java-uuid", "name": "Jugador", "access_token": "minecraft-token",
                   "refresh_token": "refresh-token", "skins": []}
        login_result = account if complete_login is None else complete_login
        with patch.object(standalone, "HTTPServer", CallbackServer), \
             patch.object(standalone.webbrowser, "open", return_value=True) as browser, \
             patch.object(mll.microsoft_account, "get_secure_login_data", return_value=(
                 "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?client_id=test-client&state=expected&code_challenge=challenge",
                 "expected", "verifier")), \
             patch.object(mll.microsoft_account, "complete_login", side_effect=login_result if isinstance(login_result, Exception) else None,
                          return_value=login_result if not isinstance(login_result, Exception) else None) as exchange, \
             patch.object(standalone, "save_microsoft_avatar"):
            result = standalone.microsoft_login(lambda _message: None, fresh=fresh)
        exchange.assert_called_once_with("test-client", None, "http://localhost:8765/callback", "ok", "verifier")
        opened = urllib.parse.urlparse(browser.call_args.args[0])
        query = urllib.parse.parse_qs(opened.query)
        self.assertEqual(["expected"], query["state"])
        self.assertEqual(["challenge"], query["code_challenge"])
        return result, query["prompt"][0]

    def test_browser_login_asks_for_account_selection(self):
        result, prompt = self._login()
        self.assertEqual("Jugador", result["name"])
        self.assertEqual("select_account", prompt)
        self.assertEqual("Jugador", standalone.selected_microsoft_account()["name"])

    def test_fresh_login_requests_credentials_on_microsoft_page(self):
        result, prompt = self._login(fresh=True)
        self.assertEqual("Jugador", result["name"])
        self.assertEqual("login", prompt)

    def test_missing_java_profile_has_specific_message(self):
        with patch.object(standalone, "HTTPServer", CallbackServer), \
             patch.object(standalone.webbrowser, "open", return_value=True), \
             patch.object(mll.microsoft_account, "get_secure_login_data", return_value=(
                 "https://login.microsoftonline.com/authorize?state=expected", "expected", "verifier")), \
             patch.object(mll.microsoft_account, "complete_login", side_effect=mll.exceptions.AccountNotOwnMinecraft):
            with self.assertRaisesRegex(ValueError, "perfil de Java Edition"):
                standalone.microsoft_login(lambda _message: None, fresh=True)
        self.assertIsNone(standalone.selected_microsoft_account())

    def test_refresh_distinguishes_expired_token_from_service_failure(self):
        with patch.object(standalone, "selected_microsoft_account", return_value={"refresh_token": "saved"}):
            with patch.object(mll.microsoft_account, "complete_refresh", side_effect=mll.exceptions.InvalidRefreshToken):
                with self.assertRaisesRegex(RuntimeError, "sesión caducó"):
                    standalone.refreshed_account(lambda _message: None)
            with patch.object(mll.microsoft_account, "complete_refresh", side_effect=ConnectionError("offline")):
                with self.assertRaisesRegex(RuntimeError, "Comprueba la conexión"):
                    standalone.refreshed_account(lambda _message: None)
            with patch.object(mll.microsoft_account, "complete_refresh", side_effect=mll.exceptions.AccountNotOwnMinecraft):
                with self.assertRaisesRegex(ValueError, "perfil de Java Edition"):
                    standalone.refreshed_account(lambda _message: None)


if __name__ == "__main__":
    unittest.main()
