import json

from cpm_settings import CUY_PLAYER_UUIDS, allow_cuy_model


def test_allow_cuy_model_preserves_other_settings_and_is_repeatable(tmp_path):
    config_path = tmp_path / "config" / "cpm.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({
        "selectedModel": "my-model.cpmmodel",
        "playerSettings": {
            "someone-else": {"maxTex": 128},
            CUY_PLAYER_UUIDS[0]: {"maxLink": 512, "custom": True},
        },
    }))

    allow_cuy_model(tmp_path)
    first = config_path.read_bytes()
    allow_cuy_model(tmp_path)
    assert config_path.read_bytes() == first

    config = json.loads(first)
    assert config["selectedModel"] == "my-model.cpmmodel"
    assert config["playerSettings"]["someone-else"] == {"maxTex": 128}
    assert config["playerSettings"][CUY_PLAYER_UUIDS[0]] == {
        "maxTex": 2048, "maxLink": 512, "custom": True,
    }
    assert config["playerSettings"][CUY_PLAYER_UUIDS[1]] == {
        "maxTex": 2048, "maxLink": 256,
    }
