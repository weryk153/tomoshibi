"""她主動開口時拿到的話題與新聞，要是現在的，不是檔案裡剩下的。

實際發生過：提示檔最後寫入是 8 月 21 日，那時抓的新聞一直留在裡面。之後設定
頁的新聞開關是關的、也沒有話題清單，但檔案只在存話題設定時才重寫，於是 40 天
後她每次主動開口都在講那時的颱風。
"""

import datetime
import json

import pytest

from src.open_llm_vtuber import news_topics as nt
from src.open_llm_vtuber import topics_route as tr

STALE_PROMPT = nt.compose_content(
    manual_topics=["天文"],
    news_blocks=[
        "台灣：\n- 沙德爾颱風路徑變了！逼近台灣機會變大",
        "科技：\n- 半導體新廠動工",
    ],
    got_any=True,
)


@pytest.fixture()
def files(tmp_path, monkeypatch):
    state = tmp_path / "proactive_topics.json"
    prompt = tmp_path / "proactive_speak_prompt.txt"
    mentioned = tmp_path / "mentioned_news.json"
    monkeypatch.setattr(tr, "STATE_PATH", str(state))
    monkeypatch.setattr(nt, "PROMPT_PATH", str(prompt))
    monkeypatch.setattr(nt, "MENTIONED_PATH", str(mentioned))
    prompt.write_text(STALE_PROMPT, encoding="utf-8")
    return state, prompt, mentioned


def _state(path, *, topics, enabled, refreshed_hours_ago):
    stamp = None
    if refreshed_hours_ago is not None:
        stamp = (
            datetime.datetime.now().astimezone()
            - datetime.timedelta(hours=refreshed_hours_ago)
        ).isoformat(timespec="seconds")
    path.write_text(
        json.dumps(
            {
                "topics": topics,
                "news": {"enabled": enabled, "interval_hours": 6},
                "last_news_refresh": stamp,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_with_no_settings_saved_the_old_news_is_not_used(files):
    prompt = tr.current_proactive_prompt()

    assert "沙德爾" not in prompt
    assert "天文" not in prompt
    assert prompt.startswith(nt.INSTRUCTION.strip()[:20])


def test_news_turned_off_is_not_used_even_if_the_file_still_has_it(files):
    state, _, _ = files
    _state(state, topics=["天文"], enabled=False, refreshed_hours_ago=1)

    prompt = tr.current_proactive_prompt()

    assert "沙德爾" not in prompt
    assert "- 天文" in prompt


def test_fresh_news_is_used(files):
    state, _, _ = files
    _state(state, topics=["天文"], enabled=True, refreshed_hours_ago=2)

    prompt = tr.current_proactive_prompt()

    assert "沙德爾颱風路徑變了" in prompt
    assert "- 天文" in prompt


def test_news_older_than_a_day_is_not_used(files):
    state, _, _ = files
    _state(state, topics=["天文"], enabled=True, refreshed_hours_ago=30)

    prompt = tr.current_proactive_prompt()

    assert "沙德爾" not in prompt
    assert "- 天文" in prompt


def test_a_headline_she_brought_up_is_not_given_again(files):
    state, _, _ = files
    _state(state, topics=[], enabled=True, refreshed_hours_ago=2)

    nt.note_mentioned(
        "你看，沙德爾颱風路徑變了，專家說逼近的機會變大。",
        tr.current_proactive_prompt(),
    )
    prompt = tr.current_proactive_prompt()

    assert "沙德爾" not in prompt
    # A category left with nothing goes too; the rest stays.
    assert "台灣：" not in prompt
    assert "半導體新廠動工" in prompt


def test_a_remark_that_mentions_no_headline_marks_nothing(files):
    state, _, _ = files
    _state(state, topics=[], enabled=True, refreshed_hours_ago=2)

    nt.note_mentioned("喂，還醒著嗎？", tr.current_proactive_prompt())

    assert "沙德爾颱風路徑變了" in tr.current_proactive_prompt()
