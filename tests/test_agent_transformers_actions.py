"""動作描寫關著時，`*…*` 整段拿掉（跨串流片段也一樣）。"""

from src.open_llm_vtuber.agent.transformers import ActionDropper


def test_actions_between_stars_are_dropped_even_across_chunks():
    dropper = ActionDropper()
    out = "".join(
        dropper.feed(part)
        for part in ["*把相", "機收起來* 那最後", "一集呢？*眨", "眼*好"]
    )
    assert out + dropper.finish() == "那最後一集呢？好"


def test_text_without_stars_passes_through():
    dropper = ActionDropper()
    assert dropper.feed("你好。") + dropper.finish() == "你好。"
