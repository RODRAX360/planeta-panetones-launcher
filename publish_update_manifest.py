"""Publish a verified release manifest to the repository's main branch."""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def request(url: str, token: str, *, method: str = "GET", payload: dict | None = None):
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
               "User-Agent": "PlanetaPanetones-release", "X-GitHub-Api-Version": "2022-11-28"}
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def publish(source: Path, target: str) -> None:
    if target not in ("launcher-update.json", "launcher-update-linux.json"):
        raise ValueError("Nombre de manifiesto inesperado.")
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    url = f"https://api.github.com/repos/{repository}/contents/{urllib.parse.quote(target)}"
    content = source.read_bytes()
    for attempt in range(5):
        try:
            current = request(url + "?ref=main", token)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            current = None
        if current and base64.b64decode(current["content"]) == content:
            print(f"{target} ya está publicado.")
            return
        payload = {"message": f"Publicar {target}", "content": base64.b64encode(content).decode("ascii"),
                   "branch": "main"}
        if current:
            payload["sha"] = current["sha"]
        try:
            request(url, token, method="PUT", payload=payload)
            print(f"Publicado {target}.")
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409, 422) or attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"No se pudo publicar {target}.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: publish_update_manifest.py ARCHIVO DESTINO")
    publish(Path(sys.argv[1]), sys.argv[2])
