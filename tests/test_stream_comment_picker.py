"""直接丟掉的、排隊的、先回哪一則。"""

import pytest

from src.open_llm_vtuber.stream.chat_source import ChatMessage
from src.open_llm_vtuber.stream.comment_picker import (
    CommentPicker,
    PickerRules,
    drop_reason,
)

_ids = iter(range(10_000))


def msg(text, author="小明", at=0.0, kind="text"):
    return ChatMessage(
        id=str(next(_ids)), author=author, text=text, timestamp=at, kind=kind
    )


@pytest.mark.parametrize(
    "text,reason",
    [
        ("看這個 https://example.com", "link"),
        ("www.example.com 好玩", "link"),
        ("去 bit.ly 看", "link"),
        ("!play", "command"),
        ("！點歌", "command"),
        ("😂😂😂", "no_words"),
        ("？？？", "no_words"),
        ("你這個笨蛋", "blocked"),
        ("BAKA desu", "blocked"),
        ("今天好冷", None),
        ("2026 快樂", None),
    ],
)
def test_drop_reasons(text, reason):
    assert drop_reason(msg(text), PickerRules(blocklist=("笨蛋", "baka"))) == reason


def test_too_long_is_dropped():
    assert drop_reason(msg("字" * 101), PickerRules()) == "too_long"
    assert drop_reason(msg("字" * 100), PickerRules()) is None


def test_same_text_twice_within_the_window_is_spam():
    picker = CommentPicker(PickerRules())
    assert picker.offer(msg("草", author="a", at=0), now=0) is None
    assert picker.offer(msg(" 草 ", author="b", at=10), now=10) == "duplicate"
    assert picker.offer(msg("草", author="c", at=50), now=50) is None
    assert (picker.read, picker.dropped, len(picker)) == (3, 1, 2)


def test_queue_limit_drops_the_oldest():
    picker = CommentPicker(PickerRules(queue_limit=2))
    for i, text in enumerate(["一", "二", "三"]):
        picker.offer(msg(text, author=str(i), at=i), now=i)
    assert len(picker) == 2
    assert picker.dropped == 1
    assert {picker.pick(3).text, picker.pick(3).text} == {"二", "三"}


def test_stale_comments_are_not_picked():
    picker = CommentPicker(PickerRules(max_age=60))
    picker.offer(msg("很久以前", at=0), now=0)
    assert picker.pick(61) is None
    assert len(picker) == 0
    assert picker.dropped == 1


def test_priority_order():
    picker = CommentPicker(PickerRules(names=("芙莉蓮",)))
    picker.offer(msg("普通的話", author="a", at=5), now=5)
    picker.offer(msg("妳喜歡魔法嗎", author="b", at=1), now=5)
    picker.offer(msg("芙莉蓮早安", author="c", at=2), now=5)
    picker.offer(msg("生日快樂", author="d", at=0, kind="paid"), now=5)
    picker.offer(msg("我是會員", author="e", at=0.5, kind="member"), now=5)
    order = [picker.pick(6).text for _ in range(5)]
    assert order == ["我是會員", "生日快樂", "芙莉蓮早安", "妳喜歡魔法嗎", "普通的話"]


def test_viewers_not_yet_answered_come_first_and_cooldown_holds():
    picker = CommentPicker(PickerRules(viewer_cooldown=120))
    picker.offer(msg("第一句", author="a", at=0), now=0)
    assert picker.pick(1).author == "a"
    picker.offer(msg("又是我", author="a", at=2), now=2)
    picker.offer(msg("我是新來的", author="b", at=1.5), now=2)
    assert picker.pick(3).author == "b"
    assert picker.pick(4) is None  # a 還在冷卻
    picker.offer(msg("我也新來的", author="c", at=100), now=100)
    assert picker.pick(100).author == "c"
    assert picker.pick(122) is None  # 「又是我」已經超過 60 秒，過期
