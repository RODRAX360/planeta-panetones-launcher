"""Release versions must always advance, even after a partial publication."""

import base64
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import ci_release_version as release_version


def encoded_manifest(version: str) -> dict:
    content = base64.b64encode(json.dumps({"version": version}).encode("utf-8"))
    return {"encoding": "base64", "content": content.decode("ascii")}


class ReleaseVersionTests(unittest.TestCase):
    def test_next_version_uses_highest_release_or_feed_after_partial_release(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "version.py"
            source.write_text('VERSION = "1.0.6"\n', encoding="utf-8")

            def github_response(url: str, _token: str):
                if "/releases?" in url:
                    return [{"tag_name": "launcher-v1.0.8"},
                            {"tag_name": "launcher-linux-v1.0.7"},
                            {"tag_name": "pack-2026.10.2"}]
                if "/contents/launcher-update-linux.json" in url:
                    return encoded_manifest("1.0.9")
                return encoded_manifest("1.0.8")

            with patch.object(release_version, "_github_json", side_effect=github_response):
                self.assertEqual(release_version.next_release_version("owner/repo", "token", source), "1.0.10")

    def test_missing_feed_is_allowed_but_invalid_feed_fails(self):
        with patch.object(release_version, "_github_json") as github:
            github.side_effect = [[], urllib.error.HTTPError("https://api.github.com", 404, "missing", {}, None),
                                  encoded_manifest("1.0.6")]
            self.assertEqual(release_version.published_versions("owner/repo", "token"), [(1, 0, 6)])

        with patch.object(release_version, "_github_json") as github:
            github.side_effect = [[], encoded_manifest("invalid")]
            with self.assertRaisesRegex(ValueError, "launcher-update.json"):
                release_version.published_versions("owner/repo", "token")

    def test_stamp_changes_only_version_assignment_and_validates_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "version.py"
            source.write_text('"""Launcher version."""\n\nVERSION = "1.0.6"\n', encoding="utf-8")
            release_version.stamp_version("1.0.7", source)
            self.assertEqual(source.read_text(encoding="utf-8"),
                             '"""Launcher version."""\n\nVERSION = "1.0.7"\n')
            with self.assertRaises(ValueError):
                release_version.stamp_version("1.0.7; print(1)", source)

    def test_prepare_writes_shared_job_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            output.touch()
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo", "GH_TOKEN": "secret",
                                         "GITHUB_OUTPUT": str(output)}), \
                    patch.object(sys, "argv", ["ci_release_version.py", "prepare"]), \
                    patch.object(release_version, "next_release_version", return_value="1.0.10"):
                release_version.main()
            self.assertEqual(output.read_text(encoding="utf-8"), "version=1.0.10\n")


if __name__ == "__main__":
    unittest.main()
