"""Create Diorama's initial client settings with its HUD hidden."""

import json
from pathlib import Path


def initialize_diorama(game_dir: Path) -> None:
    settings = game_dir / "diorama" / "config.json"
    if settings.exists():
        return
    settings.parent.mkdir(parents=True, exist_ok=True)
    temporary = settings.with_suffix(".json.part")
    temporary.write_text(json.dumps({"minimap": False}) + "\n", encoding="utf-8")
    temporary.replace(settings)
