"""protected_names 是角色設定的一個選填欄位。

用真實的預設設定檔當載體，確認它走得通實際的載入路徑；沒設這個鍵的角色
（隨附的預設就是）行為完全不變——空名單代表「不保護任何專有名詞」。
"""

import yaml

from src.open_llm_vtuber.config_manager.character import CharacterConfig

TEMPLATE = "config_templates/conf.ZH.default.yaml"


def _character_payload() -> dict:
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["character_config"]


def test_shipped_default_protects_no_names():
    """隨附的預設設定不帶任何角色名字——這正是重構要達成的狀態。"""
    character = CharacterConfig.model_validate(_character_payload())

    assert character.protected_names == {}


def test_protected_names_round_trips_from_the_character_file():
    """角色檔寫了對映就原樣讀出來，供正規化函式使用。"""
    payload = _character_payload()
    payload["protected_names"] = {"愛徠": ["愛萊", "愛崍"]}

    character = CharacterConfig.model_validate(payload)

    assert character.protected_names == {"愛徠": ["愛萊", "愛崍"]}
