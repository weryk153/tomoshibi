"""換角色模型時跟著換預設人設，但絕不蓋掉使用者自己寫的人設。"""

from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import character_route, default_personas as dp


def test_bundled_defaults_are_readable():
    template = dp.template_default()
    shino = dp.model_default("Sendagaya_Shino")
    assert template and template["persona_prompt"].strip()
    assert shino and shino["character_name"] == "篠"
    assert "千駄ヶ谷 篠" in shino["persona_prompt"]
    assert dp.model_default("mao_pro") is None  # 內建 Live2D 沒有自己的預設人設


def test_switching_to_shino_replaces_the_untouched_template_persona():
    template = dp.template_default()
    persona, name, swapped = dp.swap_for_model_change(
        "mao_pro",
        "Sendagaya_Shino",
        template["persona_prompt"],
        template["character_name"],
    )
    assert swapped
    assert persona == dp.model_default("Sendagaya_Shino")["persona_prompt"]
    assert name == "篠"


def test_trailing_whitespace_does_not_count_as_an_edit():
    template = dp.template_default()
    persona, _, swapped = dp.swap_for_model_change(
        "mao_pro", "Sendagaya_Shino", template["persona_prompt"].rstrip() + "\n\n", "AI"
    )
    assert swapped


def test_a_persona_the_user_wrote_is_never_replaced():
    mine = "你是我自己寫的角色。"
    persona, name, swapped = dp.swap_for_model_change(
        "mao_pro", "Sendagaya_Shino", mine, "我的角色"
    )
    assert (persona, name, swapped) == (mine, "我的角色", False)


def test_switching_back_from_shino_restores_the_generic_persona():
    template = dp.template_default()
    shino = dp.model_default("Sendagaya_Shino")
    persona, name, swapped = dp.swap_for_model_change(
        "Sendagaya_Shino", "mao_pro", shino["persona_prompt"], "篠"
    )
    assert swapped
    assert persona == template["persona_prompt"]
    assert name == template["character_name"]


def test_custom_display_name_survives_a_persona_swap():
    template = dp.template_default()
    _, name, swapped = dp.swap_for_model_change(
        "mao_pro", "Sendagaya_Shino", template["persona_prompt"], "小燈"
    )
    assert swapped and name == "小燈"


def test_same_model_or_unsafe_names_do_nothing():
    template = dp.template_default()
    assert (
        dp.swap_for_model_change(
            "mao_pro", "mao_pro", template["persona_prompt"], "AI"
        )[2]
        is False
    )
    assert dp.model_default("../config_templates") is None
    assert dp.model_default("vrm-models/Sendagaya_Shino") is None


@pytest.mark.parametrize("filename", ["conf.yaml", "companion.yaml"])
@pytest.mark.parametrize("custom_persona", [False, True])
def test_model_change_persists_persona_and_preserves_identity(
    tmp_path, monkeypatch, filename, custom_persona
):
    template = dp.template_default()
    shino = dp.model_default("Sendagaya_Shino")
    monkeypatch.setattr(dp, "TEMPLATE_PATH", str(Path(dp.TEMPLATE_PATH).resolve()))
    monkeypatch.setattr(
        dp, "MODEL_ROOTS", tuple(str(Path(root).resolve()) for root in dp.MODEL_ROOTS)
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(character_route, "_is_local_request", lambda request: True)
    monkeypatch.setattr(character_route, "_rescan_skins", lambda: None)
    monkeypatch.setattr(
        character_route,
        "_load_model_dict",
        lambda: [{"name": "mao_pro"}, {"name": "Sendagaya_Shino"}],
    )
    path = tmp_path / filename
    if filename != "conf.yaml":
        path = tmp_path / "characters" / filename
        path.parent.mkdir()
    prompt = "你是我自己寫的角色。" if custom_persona else template["persona_prompt"]
    original = {
        "conf_uid": "stable_identity",
        "conf_name": "我的夥伴",
        "character_name": template["character_name"],
        "persona_prompt": prompt,
        "live2d_model_name": "mao_pro",
        "avatar": "my-avatar.png",
        "reply_language": "Japanese",
    }
    path.write_text(yaml.safe_dump({"character_config": original}), encoding="utf-8")
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    with TestClient(app) as client:
        response = client.put(
            f"/api/characters/{filename}",
            json={
                "conf_name": original["conf_name"],
                "persona_prompt": prompt,
                "live2d_model_name": "Sendagaya_Shino",
            },
        )
    assert response.status_code == 200, response.text
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))["character_config"]
    expected = original if custom_persona else shino
    assert saved["persona_prompt"].strip() == expected["persona_prompt"].strip()
    assert saved["character_name"] == expected["character_name"]
    assert saved["live2d_model_name"] == "Sendagaya_Shino"
    for key in ("conf_uid", "conf_name", "avatar", "reply_language"):
        assert saved[key] == original[key]
