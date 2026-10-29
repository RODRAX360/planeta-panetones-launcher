"""Check that Windows releases never embed an unusable pack location."""

import json
import unittest
from unittest.mock import patch

from build_release_windows import release_urls, verify_pack_manifest


class _Response:
    def __init__(self, url: str, payload: dict):
        self.url = url
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, _limit):
        return self.payload


class WindowsReleaseTests(unittest.TestCase):
    def test_release_urls_and_rejects_insecure_address(self):
        self.assertEqual(release_urls("https://example.org/pack/"), (
            "https://example.org/pack/manifest.json",
            "https://example.org/pack/optimizado/manifest.json",
            "https://example.org/pack/launcher-update.json",
        ))
        for url in ("http://example.org/pack", "https://user@example.org/pack",
                    "https://example.org/pack?x=1"):
            with self.assertRaises(ValueError):
                release_urls(url)

    def test_pack_manifest_must_match_edition_and_stay_on_https(self):
        url = "https://example.org/pack/optimizado/manifest.json"
        payload = {"schema": 1, "minecraft": "1.20.1", "forge": "47.4.20",
                   "edition": "optimizada", "files": []}
        with patch("build_release_windows.urllib.request.urlopen", return_value=_Response(url, payload)):
            verify_pack_manifest(url, "optimizada")
            with self.assertRaises(ValueError):
                verify_pack_manifest(url, "principal")
        with patch("build_release_windows.urllib.request.urlopen",
                   return_value=_Response("http://example.org/manifest.json", payload)):
            with self.assertRaises(ValueError):
                verify_pack_manifest(url, "optimizada")


if __name__ == "__main__":
    unittest.main()
