"""The first Play installs a Release archive; later plays reuse verified files."""

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from updater import sync_pack


class _Response(io.BytesIO):
    def __init__(self, url: str, data: bytes):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class ArchivePackTests(unittest.TestCase):
    def test_downloads_on_first_play_and_reuses_installed_file(self):
        data = b"forge mod data"
        archive_io = io.BytesIO()
        with zipfile.ZipFile(archive_io, "w") as bundle:
            bundle.writestr("mods/example.jar", data)
        archive_bytes = archive_io.getvalue()
        manifest_url = "https://raw.githubusercontent.com/test/pack/main/manifest.json"
        archive_url = "https://github.com/test/pack/releases/download/v1/pack-principal.zip"
        manifest = {
            "schema": 1, "edition": "principal", "minecraft": "1.20.1", "forge": "47.4.20",
            "files": [{"path": "mods/example.jar", "size": len(data),
                       "sha256": hashlib.sha256(data).hexdigest()}],
            "archive": {"url": archive_url, "size": len(archive_bytes),
                        "sha256": hashlib.sha256(archive_bytes).hexdigest()},
        }
        requests = []

        def urlopen(url, timeout):
            requests.append(url)
            if url == manifest_url:
                return _Response(url, json.dumps(manifest).encode())
            if url == archive_url:
                return _Response(url, archive_bytes)
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as temporary, patch("updater.urllib.request.urlopen", side_effect=urlopen):
            game = Path(temporary)
            sync_pack(manifest_url, game, lambda *_args: None, expected_edition="principal")
            self.assertEqual((game / "mods/example.jar").read_bytes(), data)
            sync_pack(manifest_url, game, lambda *_args: None, expected_edition="principal")
            self.assertEqual(requests, [manifest_url, archive_url, manifest_url])
            (game / "mods/example.jar").write_bytes(b"damaged")
            sync_pack(manifest_url, game, lambda *_args: None, expected_edition="principal")
            self.assertEqual((game / "mods/example.jar").read_bytes(), data)
            self.assertEqual(requests[-2:], [manifest_url, archive_url])


if __name__ == "__main__":
    unittest.main()
