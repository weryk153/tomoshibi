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


def test_actions_in_brackets_are_dropped_too():
    """關著動作描寫時，她改用括號寫：（偷偷瞄了你一眼，又迅速轉開視線）。"""
    dropper = ActionDropper()
    parts = ["（偷偷瞄了你一", "眼，又迅速轉開視線）那個……", "(blush) 沒事啦。"]
    out = "".join(dropper.feed(part) for part in parts) + dropper.finish()
    assert out == "那個……沒事啦。"
