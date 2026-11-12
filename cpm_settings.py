"""Allow the published Cuy CPM model for its owner without relaxing other players."""

import json
from pathlib import Path


CUY_PLAYER_UUIDS = (
    "b7146297-5e54-3f08-9b8e-b981431db8f0",  # Offline-mode server UUID.
    "9e5dc3f2-2ab7-4b5d-8153-544467a86f1e",  # Online account UUID.
)


def allow_cuy_model(game_dir: Path) -> None:
    config_path = game_dir / "config" / "cpm.json"
    if not config_path.is_file():
        return
    config = json.loads(config_path.read_text(encoding="utf-8"))
    players = config.setdefault("playerSettings", {})
    changed = False
    for uuid in CUY_PLAYER_UUIDS:
        settings = players.setdefault(uuid, {})
        if settings.get("maxTex", 0) < 2048:
            settings["maxTex"] = 2048
            changed = True
        if settings.get("maxLink", 0) < 256:
            settings["maxLink"] = 256
            changed = True
    if changed:
        temporary = config_path.with_suffix(".json.part")
        temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(config_path)
