"""merge_self_memory：把這輪分類出來的 self 行合併進既有的 self 記憶。

背景（實測，見 fix-round-5-brief.md）：9B 模型輸出「更新後的完整記憶」時，
收到「現有記憶」後只吐這一輪的內容、舊條目直接丟——連舊提示詞都一樣。所以
她自己的記憶不能靠模型改寫，要程式端保留舊條目、只在真的相近時才用新的
蓋掉舊的那一行。
"""

from src.open_llm_vtuber.memory_core import SELF_CAP_CHARS, merge_self_memory

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


# --- fix round 5b: 一條新行貼近多條舊行 ------------------------------------


def test_new_line_matching_two_existing_lines_replaces_best_match_and_drops_the_rest():
    """新行同時貼近兩條舊行（同一件事的兩份舊紀錄）：只留新的那行，取代 ratio
    最高的那條位置，另一條不能當殘留的重複行留下來。"""
    existing = f"{NAME}：喜歡喝咖啡。\n{NAME}：很喜歡喝咖啡。"
    incoming = f"{NAME}：超喜歡喝咖啡。"
    merged = merge_self_memory(existing, incoming)
    assert merged == incoming
    assert merged.count("喝咖啡") == 1


def test_new_line_best_match_is_the_second_existing_line_position_preserved():
    """最佳匹配是第二條舊行時，新行落在第二條的位置（在第三條之前）；
    第一條舊行雖然也超過門檻，一樣要被刪掉，不留重複。"""
    existing = f"{NAME}：很喜歡咖啡。\n{NAME}：真的很喜歡咖啡。\n{NAME}：討厭夏天。"
    incoming = f"{NAME}：超級真的很喜歡咖啡。"
    merged = merge_self_memory(existing, incoming)
    assert merged.splitlines() == [incoming, f"{NAME}：討厭夏天。"]


# --- fix round 5b: 單一新行本身就超過 cap ------------------------------------


def test_oversized_single_new_line_leaves_existing_memory_unchanged():
    """新行單獨就超過 cap：丟光可丟的舊行後還是超過，代表這輪內容放不進去，
    整份記憶維持原樣，而不是靜默回傳空字串或截斷過的內容。"""
    existing = f"{NAME}：喜歡咖啡。"
    incoming = f"{NAME}：" + "資" * 900
    merged = merge_self_memory(existing, incoming, cap=SELF_CAP_CHARS)
    assert merged == existing


def test_full_existing_file_evicts_oldest_lines_but_keeps_the_new_line():
    """既有記憶已經塞滿，新行仍然要進得去：從最舊的（最前面的）未被這輪動過
    的行開始丟，直到擠得下新行為止。"""
    existing = "\n".join(
        f"{NAME}：舊事{i}，這是完整的一句敘述用來撐長度。" for i in range(10)
    )
    incoming = f"{NAME}：今天發生的新事。"
    cap = len(existing)  # 不丟舊行的話新行進不去
    merged = merge_self_memory(existing, incoming, cap=cap)
    assert incoming in merged
    assert len(merged) <= cap
    assert existing.splitlines()[0] not in merged.splitlines()
