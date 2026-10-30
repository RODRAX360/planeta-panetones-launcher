"""An older CI run must never move an update feed backwards."""

import base64
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import publish_update_manifest


def remote_manifest(version: str) -> dict:
    content = json.dumps({"version": version}).encode("utf-8")
    return {"sha": "current-sha", "content": base64.b64encode(content).decode("ascii")}


class PublishUpdateManifestTests(unittest.TestCase):
    def test_newer_feed_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "update.json"
            source.write_text('{"version":"1.0.7"}', encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_TOKEN": "token", "GITHUB_REPOSITORY": "owner/repo"}), \
                    patch.object(publish_update_manifest, "request", return_value=remote_manifest("1.0.8")) as github:
                publish_update_manifest.publish(source, "launcher-update.json")
            self.assertEqual(github.call_count, 1)
            self.assertEqual(github.call_args.kwargs.get("method", "GET"), "GET")

    def test_conflicting_publish_rechecks_feed_before_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "update.json"
            source.write_text('{"version":"1.0.7"}', encoding="utf-8")
            reads = iter((remote_manifest("1.0.6"), remote_manifest("1.0.8")))
            writes = []

            def github_request(_url, _token, *, method="GET", payload=None):
                if method == "GET":
                    return next(reads)
                writes.append(payload)
                raise urllib.error.HTTPError("https://api.github.com", 409, "conflict", {}, None)

            with patch.dict(os.environ, {"GITHUB_TOKEN": "token", "GITHUB_REPOSITORY": "owner/repo"}), \
                    patch.object(publish_update_manifest, "request", side_effect=github_request), \
                    patch.object(publish_update_manifest.time, "sleep"):
                publish_update_manifest.publish(source, "launcher-update-linux.json")
            self.assertEqual(len(writes), 1)


if __name__ == "__main__":
    unittest.main()
