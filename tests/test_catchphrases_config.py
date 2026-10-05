"""catchphrases 是角色設定的一個選填欄位。

跟 protected_names 走同一條線（見 test_protected_names_config.py）：用真實的
預設設定檔當載體，確認它走得通實際的載入路徑；沒設這個鍵的角色（隨附的預設
就是）行為完全不變——空字典代表「不保留任何口頭禪」。
"""

import yaml

from src.open_llm_vtuber.config_manager.character import CharacterConfig

TEMPLATE = "config_templates/conf.ZH.default.yaml"


def _character_payload() -> dict:
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["character_config"]


def test_shipped_default_keeps_no_catchphrases():
    """隨附的預設設定不帶任何口頭禪——這正是這個功能要達成的狀態。"""
    character = CharacterConfig.model_validate(_character_payload())

    assert character.catchphrases == {}


def test_catchphrases_round_trips_from_the_character_file():
    """角色檔寫了對照表就原樣讀出來，供翻譯器使用。"""
    payload = _character_payload()
    payload["catchphrases"] = {"nya": "にゃ"}

    character = CharacterConfig.model_validate(payload)

    assert character.catchphrases == {"nya": "にゃ"}
