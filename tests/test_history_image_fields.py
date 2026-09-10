from __future__ import annotations

import json

import pytest

from src.open_llm_vtuber.chat_history_manager import (
    create_new_history,
    get_history,
    store_message,
)


CONF_UID = "aoi"


@pytest.fixture(autouse=True)
def _in_tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_an_image_message_round_trips():
    history_uid = create_new_history(CONF_UID)

    store_message(
        CONF_UID,
        history_uid,
        "ai",
        "（畫了一張圖：1girl, red hair）",
        message_type="image",
        image="/generated-images/abc.png",
    )

    (stored,) = get_history(CONF_UID, history_uid)
    assert stored["type"] == "image"
    assert stored["image"] == "/generated-images/abc.png"
    assert stored["content"] == "（畫了一張圖：1girl, red hair）"
    assert stored["role"] == "ai"


def test_a_plain_message_is_still_written_as_text():
    history_uid = create_new_history(CONF_UID)

    store_message(CONF_UID, history_uid, "human", "嗨")

    (stored,) = get_history(CONF_UID, history_uid)
    assert stored["type"] == "text"
    assert stored["image"] is None


def test_history_files_written_before_this_feature_still_load():
    """舊檔沒有 type/image 欄位，不做遷移——缺欄位即文字訊息。"""
    history_uid = create_new_history(CONF_UID)
    path = f"chat_history/{CONF_UID}/{history_uid}.json"
    legacy = [
        {"role": "metadata", "timestamp": "2026-01-01T00:00:00"},
        {"role": "human", "timestamp": "2026-01-01T00:00:01", "content": "舊訊息"},
    ]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(legacy, handle, ensure_ascii=False)

    (stored,) = get_history(CONF_UID, history_uid)
    assert stored["content"] == "舊訊息"
    assert stored.get("type") in (None, "text")


def test_an_image_message_survives_alongside_text_messages():
    history_uid = create_new_history(CONF_UID)

    store_message(CONF_UID, history_uid, "human", "畫張你自己")
    store_message(CONF_UID, history_uid, "ai", "行吧，等我一下。")
    store_message(
        CONF_UID,
        history_uid,
        "ai",
        "（畫了一張圖：1girl, red hair）",
        message_type="image",
        image="/generated-images/abc.png",
    )

    stored = get_history(CONF_UID, history_uid)
    assert [m.get("type") for m in stored] == ["text", "text", "image"]
    assert stored[2]["image"] == "/generated-images/abc.png"
