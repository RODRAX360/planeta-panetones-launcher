"""The host's powered-off placeholder must not appear online in the launcher."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server_status import query_server


class ServerStatusTests(unittest.TestCase):
    def test_host_placeholder_is_offline_and_keeps_address(self):
        response = SimpleNamespace(players=SimpleNamespace(online=0, max=0), latency=64)
        with patch("server_status.JavaServer.lookup") as lookup:
            lookup.return_value.status.return_value = response
            status = query_server(" nodo2.axolthost.com:25568 ")
        self.assertFalse(status["online"])
        self.assertEqual(status["message"], "Servidor apagado")
        self.assertEqual(status["address"], "nodo2.axolthost.com:25568")


if __name__ == "__main__":
    unittest.main()
