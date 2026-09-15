"""merge_self_memory：把這輪分類出來的 self 行合併進既有的 self 記憶。

背景（實測，見 fix-round-5-brief.md）：9B 模型輸出「更新後的完整記憶」時，
收到「現有記憶」後只吐這一輪的內容、舊條目直接丟——連舊提示詞都一樣。所以
她自己的記憶不能靠模型改寫，要程式端保留舊條目、只在真的相近時才用新的
蓋掉舊的那一行。
"""

from src.open_llm_vtuber.memory_core import merge_self_memory

NAME = "紅莉栖"


def test_new_unrelated_line_is_appended_after_existing_lines_in_order():
    existing = f"{NAME}：喜歡咖啡。\n{NAME}：討厭夏天。"
    incoming = f"{NAME}：怕蟑螂。"
    merged = merge_self_memory(existing, incoming)
    assert merged == f"{NAME}：喜歡咖啡。\n{NAME}：討厭夏天。\n{NAME}：怕蟑螂。"


def test_similar_line_replaces_the_old_one_in_place():
    existing = f"{NAME}：喜歡咖啡。\n{NAME}：討厭夏天。"
    incoming = f"{NAME}：喜歡喝咖啡。"
    merged = merge_self_memory(existing, incoming)
    assert merged == f"{incoming}\n{NAME}：討厭夏天。"


def test_identical_line_is_not_duplicated():
    existing = f"{NAME}：喜歡咖啡。\n{NAME}：討厭夏天。"
    incoming = f"{NAME}：喜歡咖啡。"
    merged = merge_self_memory(existing, incoming)
    assert merged == existing
    assert merged.count("喜歡咖啡") == 1


def test_empty_incoming_returns_existing_unchanged():
    existing = f"{NAME}：喜歡咖啡。"
    assert merge_self_memory(existing, "") == existing
    assert merge_self_memory(existing, "   \n  ") == existing


def test_empty_existing_returns_incoming():
    incoming = f"{NAME}：喜歡咖啡。\n{NAME}：討厭夏天。"
    assert merge_self_memory("", incoming) == incoming


def test_over_cap_drops_oldest_lines_first_and_keeps_the_new_line():
    existing = "\n".join(f"{NAME}：舊事{i}。" * 5 for i in range(20))
    incoming = f"{NAME}：新事一件。"
    merged = merge_self_memory(existing, incoming, cap=100)
    assert len(merged) <= 100
    assert incoming in merged
    # 最舊的行（existing 的第一行）該先被丟掉
    assert existing.splitlines()[0] not in merged.splitlines()


def test_multiple_new_lines_each_evaluated_independently():
    existing = f"{NAME}：喜歡咖啡。"
    incoming = f"{NAME}：很喜歡喝咖啡。\n{NAME}：怕蟑螂。"
    merged = merge_self_memory(existing, incoming)
    lines = merged.splitlines()
    assert lines[0] == f"{NAME}：很喜歡喝咖啡。"
    assert lines[1] == f"{NAME}：怕蟑螂。"
    assert len(lines) == 2
