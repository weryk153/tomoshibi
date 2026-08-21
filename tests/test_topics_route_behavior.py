"""主動話題設定的狀態與組裝——重寫前的特徵測試。

這個模組原本一個測試都沒有（521 行）。這些先在舊實作上跑綠，釘住行為契約：

- 空的話題清單就是空的，絕不偷偷塞回預設。這是整個設計的重點：舊版用
  ``or DEFAULT_CATEGORIES`` 兜底，結果那四個預設分類刪不掉。
- 清單會去空白、去重、限長、限量，順序保留。
- 舊格式（manual_topics + news.categories 兩份清單）要合併進單一清單，
  升級的使用者不會掉東西。
- 壞掉的狀態檔當預設處理，不能讓設定頁整個打不開。
- 話題對到「精選查詢字」時用對照後的查詢（AI → AI 人工智慧），沒對到的
  就拿使用者原字去查。
- 狀態檔原子寫入。
"""

import json

import pytest

from src.open_llm_vtuber import topics_route as tr


@pytest.fixture()
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "proactive_topics.json"
    monkeypatch.setattr(tr, "STATE_PATH", str(path))
    return path


# --- 清單整理 ----------------------------------------------------------------


def test_empty_stays_empty():
    # 舊版的 `or DEFAULT_CATEGORIES` 兜底讓預設分類刪不掉。空就是空。
    assert tr._sanitize_topics([]) == []
    assert tr._sanitize_topics(None) == []


def test_entries_are_trimmed_deduped_and_ordered():
    result = tr._sanitize_topics(["  科技 ", "科技", "", "  ", "AI"])

    assert result == ["科技", "AI"]


def test_count_is_capped():
    result = tr._sanitize_topics([f"主題{i}" for i in range(tr.MAX_TOPICS + 10)])

    assert len(result) == tr.MAX_TOPICS


def test_each_entry_is_length_capped():
    result = tr._sanitize_topics(["長" * (tr.MAX_TOPIC_LEN + 50)])

    assert len(result[0]) == tr.MAX_TOPIC_LEN


def test_non_strings_are_dropped():
    assert tr._sanitize_topics(["好的", 123, None, {"a": 1}]) == ["好的"]


# --- 間隔 --------------------------------------------------------------------


def test_interval_is_clamped_and_fails_soft():
    assert tr._clamp_interval(0) == tr.MIN_INTERVAL_HOURS
    assert tr._clamp_interval(999) == tr.MAX_INTERVAL_HOURS
    assert tr._clamp_interval("garbage") == tr.DEFAULT_INTERVAL_HOURS
    assert tr._clamp_interval(None) == tr.DEFAULT_INTERVAL_HOURS
    assert tr._clamp_interval(6.4) == 6


# --- 狀態檔 ------------------------------------------------------------------


def test_missing_file_gives_defaults(state_file):
    state = tr._load_state()

    assert state["topics"] == []
    assert state["news"]["enabled"] is False
    assert state["news"]["interval_hours"] == tr.DEFAULT_INTERVAL_HOURS


def test_unreadable_file_falls_back_to_defaults(state_file):
    state_file.write_text("{ this is not json", encoding="utf-8")

    assert tr._load_state()["topics"] == []


def test_roundtrip_through_the_state_file(state_file):
    tr._write_state(
        {
            "topics": ["科技", "AI"],
            "news": {"enabled": True, "interval_hours": 12},
            "last_news_refresh": "2026-08-21T10:00:00+08:00",
        }
    )
    state = tr._load_state()

    assert state["topics"] == ["科技", "AI"]
    assert state["news"] == {"enabled": True, "interval_hours": 12}
    assert state["last_news_refresh"] == "2026-08-21T10:00:00+08:00"


def test_write_leaves_no_temp_file(state_file):
    tr._write_state(tr._default_state())

    assert state_file.exists()
    assert not list(state_file.parent.glob("*.tmp"))


def test_legacy_split_lists_are_merged(state_file):
    # 舊格式：手動話題與新聞分類是兩份清單。升級後要合併成一份，順序是手動在前。
    state_file.write_text(
        json.dumps(
            {
                "manual_topics": ["我的話題"],
                "news": {"enabled": True, "categories": ["科技", "我的話題"]},
            }
        ),
        encoding="utf-8",
    )

    state = tr._load_state()

    assert state["topics"] == ["我的話題", "科技"]
    assert state["news"]["enabled"] is True


def test_new_key_wins_over_legacy_pair(state_file):
    state_file.write_text(
        json.dumps({"topics": ["新的"], "manual_topics": ["舊的"]}),
        encoding="utf-8",
    )

    assert tr._load_state()["topics"] == ["新的"]


def test_out_of_range_interval_in_file_is_clamped_on_load(state_file):
    state_file.write_text(
        json.dumps({"news": {"enabled": True, "interval_hours": 500}}),
        encoding="utf-8",
    )

    assert tr._load_state()["news"]["interval_hours"] == tr.MAX_INTERVAL_HOURS


# --- 話題 → 查詢字 ------------------------------------------------------------


def test_curated_topics_use_the_mapped_query(monkeypatch):
    captured = {}

    def fake_fetch(categories, per_cat, seen, new_titles):
        captured["categories"] = categories
        return ["區塊"], True

    monkeypatch.setattr(tr._get_news_module(), "fetch_news_blocks", fake_fetch)

    tr._fetch_blocks_for(["AI"])

    # 標籤留使用者看到的字，查詢字換成精選過的。
    assert captured["categories"] == [("AI", "AI 人工智慧")]


def test_free_text_topics_are_searched_verbatim(monkeypatch):
    captured = {}

    def fake_fetch(categories, per_cat, seen, new_titles):
        captured["categories"] = categories
        return [], False

    monkeypatch.setattr(tr._get_news_module(), "fetch_news_blocks", fake_fetch)

    tr._fetch_blocks_for(["台南美食"])

    assert captured["categories"] == [("台南美食", "台南美食")]


def test_no_topics_fetches_nothing(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("空清單不該去抓新聞")

    monkeypatch.setattr(tr._get_news_module(), "fetch_news_blocks", explode)

    assert tr._fetch_blocks_for([]) == ([], False)
