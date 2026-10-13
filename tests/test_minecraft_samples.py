"""每一輪的樣本：看到什麼、原本寫了什麼、抓到什麼目標、身體回報什麼。"""

import json

from src.open_llm_vtuber.minecraft import samples


def test_sample_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    samples.start(
        "yura",
        "idle",
        ["你在遊戲裡目前的狀態：血量 20/20"],
        {"gameplay": {"health": 20}, "extra": 1},
        "collect 10 oak logs",
    )
    samples.raw_sentence("[minecraft_do: collect 10 oak logs] ")
    samples.raw_sentence("先把木頭收齊。")
    samples.goals(["collect 10 oak logs"])
    samples.finish("ok")
    samples.outcome("On it! !collectBlocks(oak_log, 10)")
    lines = [
        json.loads(line)
        for line in open(
            tmp_path / "chat_history/yura/minecraft_samples.jsonl", encoding="utf-8"
        )
    ]
    assert len(lines) == 2
    sample, out = lines
    assert sample["kind"] == "idle" and sample["wrote_goal"] is True
    assert sample["raw_reply"] == "[minecraft_do: collect 10 oak logs] 先把木頭收齊。"
    assert (
        sample["goals"] == ["collect 10 oak logs"]
        and sample["suggested_goal"] == "collect 10 oak logs"
    )
    assert sample["state"] == {"gameplay": {"health": 20}}
    assert out["outcome_of"] == sample["id"] and "collectBlocks" in out["body_reply"]


def test_turn_without_goal_is_kept_as_negative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    samples.start(
        "yura",
        "event",
        ["遊戲裡剛發生：\n- 天黑了"],
        None,
        "dig into the hillside and make a small shelter",
    )
    samples.raw_sentence("哇，天黑了。")
    samples.finish("ok")
    sample = json.loads(
        open(
            tmp_path / "chat_history/yura/minecraft_samples.jsonl", encoding="utf-8"
        ).readline()
    )
    assert (
        sample["wrote_goal"] is False
        and sample["goals"] == []
        and sample["state"] is None
    )


def test_outside_a_turn_nothing_breaks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    samples.raw_sentence("x")
    samples.goals(["y"])
    samples.finish("ok")
    assert not (tmp_path / "chat_history").exists()
