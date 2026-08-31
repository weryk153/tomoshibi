"""新聞話題模組的特徵測試。

寫在重寫之前、在舊實作上跑綠。釘的是行為契約：

- 標題正規化要吃掉 Google News 的「 - 來源」「 | 來源」尾綴，seen 的比對才對得上。
- 已端過的新聞不再端第二次（跨輪去重），而且只有真的端出去才記進 seen。
- seen 記錄要汰舊：超過時間窗、或超過筆數上限。
- 任何一類抓失敗只略過那一類，不中斷其他類。
- prompt 檔是原子寫入——絕不留下半截的壞檔（她每次主動說話都會重讀它）。
"""

import datetime
from src.open_llm_vtuber import news_topics as nt


# --- 標題正規化 -------------------------------------------------------------


def test_source_suffix_is_stripped():
    assert nt.normalize_title("台積電法說會登場 - 中央社") == "台積電法說會登場"
    assert nt.normalize_title("新番速報 | 巴哈姆特") == "新番速報"


def test_normalize_is_idempotent_and_handles_entities():
    once = nt.normalize_title("AT&amp;T 財報 - 路透")
    assert once == "AT&T 財報"
    assert nt.normalize_title(once) == once


def test_normalize_tolerates_none_and_blank():
    assert nt.normalize_title(None) == ""
    assert nt.normalize_title("   ") == ""


# --- seen 汰舊 --------------------------------------------------------------


def test_prune_drops_entries_older_than_the_window():
    now = datetime.datetime.now().astimezone()
    old = (now - datetime.timedelta(days=nt.SEEN_TTL_DAYS + 1)).isoformat()
    fresh = now.isoformat()

    kept = nt._prune_seen({"舊聞": old, "新聞": fresh})

    assert "舊聞" not in kept
    assert "新聞" in kept


def test_prune_caps_the_total_count_keeping_newest():
    now = datetime.datetime.now().astimezone()
    seen = {
        f"標題{i}": (now - datetime.timedelta(minutes=i)).isoformat()
        for i in range(nt.SEEN_MAX + 20)
    }

    kept = nt._prune_seen(seen)

    assert len(kept) == nt.SEEN_MAX
    assert "標題0" in kept  # 最新的留著
    assert f"標題{nt.SEEN_MAX + 19}" not in kept  # 最舊的被丟掉


def test_broken_timestamp_is_kept_not_crashed():
    kept = nt._prune_seen({"沒有時間戳": "", "亂寫": "not-a-date"})

    assert set(kept) == {"沒有時間戳", "亂寫"}


def test_mark_seen_normalizes_before_storing():
    seen = nt.mark_seen({}, ["某某事件 - 自由時報"])

    assert "某某事件" in seen


# --- 抓取與去重 -------------------------------------------------------------


def test_previously_served_titles_are_not_served_again(monkeypatch):
    monkeypatch.setattr(
        nt, "fetch_titles", lambda q, n: ["昨天就端過的 - 來源", "今天的新料"]
    )

    new_titles = []
    blocks, got_any = nt.fetch_news_blocks(
        categories=[("測試", "測試")],
        per_cat=5,
        seen={"昨天就端過的": "2026-08-21T00:00:00+08:00"},
        new_titles=new_titles,
    )

    assert got_any is True
    assert "今天的新料" in blocks[0]
    assert "昨天就端過的" not in blocks[0]
    assert new_titles == ["今天的新料"]


def test_the_same_story_is_not_repeated_across_categories(monkeypatch):
    monkeypatch.setattr(nt, "fetch_titles", lambda q, n: ["同一則新聞"])

    blocks, _ = nt.fetch_news_blocks(categories=[("甲", "甲"), ("乙", "乙")], per_cat=3)

    # 第一類拿到，第二類整個沒有內容可放，於是不產生區塊。
    assert len(blocks) == 1


def test_one_failing_category_does_not_stop_the_others(monkeypatch):
    def flaky(query, limit):
        if query == "壞掉":
            raise RuntimeError("network down")
        return ["正常的新聞"]

    monkeypatch.setattr(nt, "fetch_titles", flaky)

    blocks, got_any = nt.fetch_news_blocks(
        categories=[("壞", "壞掉"), ("好", "好的")], per_cat=3
    )

    assert got_any is True
    assert len(blocks) == 1
    assert "正常的新聞" in blocks[0]


def test_nothing_fetched_reports_no_news(monkeypatch):
    monkeypatch.setattr(nt, "fetch_titles", lambda q, n: [])

    blocks, got_any = nt.fetch_news_blocks(categories=[("空", "空")], per_cat=3)

    assert blocks == []
    assert got_any is False


# --- 寫檔 -------------------------------------------------------------------


def test_prompt_write_is_atomic(tmp_path, monkeypatch):
    # 她每次主動說話都重讀這個檔；寫到一半被中斷會留下壞檔。
    target = tmp_path / "proactive_speak_prompt.txt"
    monkeypatch.setattr(nt, "PROMPT_PATH", str(target))

    nt.write_prompt("內容")

    assert target.read_text(encoding="utf-8") == "內容"
    assert not (tmp_path / "proactive_speak_prompt.txt.tmp").exists()
