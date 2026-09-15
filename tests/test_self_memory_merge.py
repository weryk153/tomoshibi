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
    # 兩邊剝掉前綴後都要有 6 字以上，短句無法判斷相似度（見
    # test_distinct_short_facts_never_evict_each_other）。
    existing = f"{NAME}：喜歡喝咖啡。\n{NAME}：討厭夏天。"
    incoming = f"{NAME}：很喜歡喝咖啡。"
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
    existing = f"{NAME}：喜歡喝咖啡。"
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
    existing = f"{NAME}：很喜歡喝咖啡。\n{NAME}：喜歡喝咖啡。\n{NAME}：討厭夏天。"
    incoming = f"{NAME}：超喜歡喝咖啡。"
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


# --- final fix wave F2: 超上限時不可以整輪丟掉 --------------------------------

# 每行必須是真的不同的事實：內容只差一兩個字的行會被同輪去重合併掉，測不到
# 「超過 cap 時丟掉最舊的新行」這件事。
_THIRTY_DISTINCT_CHARS = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥天地玄黃宇宙洪荒"


def test_oversized_incoming_into_empty_file_keeps_the_newest_lines():
    """首次遷移（既有 self 檔是空的）時整輪 self 內容一次湧入，總長超過 cap。

    舊行沒得淘汰時舊實作直接 break、回傳 existing（空字串），於是 self 記憶
    永遠寫不進去，而且每一輪都重複同一個形狀。改成從這輪最早的新行開始丟，
    留下裝得下的最後幾行。
    """
    incoming = "\n".join(f"{NAME}：{c * 28}。" for c in _THIRTY_DISTINCT_CHARS)
    assert len(incoming) > SELF_CAP_CHARS
    merged = merge_self_memory("", incoming, cap=SELF_CAP_CHARS)
    assert merged, "整輪內容不可以被丟光"
    assert len(merged) <= SELF_CAP_CHARS
    # 保留的是最後面（最新）的行，丟掉的是最前面（最舊）的
    assert incoming.splitlines()[-1] in merged.splitlines()
    assert incoming.splitlines()[0] not in merged.splitlines()


def test_every_existing_line_matched_still_lands_the_round():
    """每一條舊行都被這輪配對到（沒有可淘汰的舊行）而總長仍超過 cap 時，
    舊實作一樣 break 掉整輪。現在要從最早的新行開始丟，結果仍然非空。"""
    six = _THIRTY_DISTINCT_CHARS[:6]
    existing = "\n".join(f"{NAME}：{c * 6}的舊版說法在這裡。" for c in six)
    incoming = "\n".join(f"{NAME}：{c * 6}的新版說法在這裡。" for c in six)
    cap = len(existing) // 2
    merged = merge_self_memory(existing, incoming, cap=cap)
    assert merged
    assert len(merged) <= cap
    assert incoming.splitlines()[-1] in merged.splitlines()


# --- final fix wave F3: 門檻、角色名前綴、同輪去重 ----------------------------

_FACTS = (
    "喜歡貓。",
    "喜歡狗。",
    "喜歡咖啡。",
    "喜歡紅茶。",
    "討厭夏天。",
    "最近迷上手沖咖啡。",
    "最近迷上手沖紅茶。",
)


def test_distinct_short_facts_never_evict_each_other():
    """性質測試：一組互不相同的短事實，任意插入其中一條新的，都不可以讓
    另一條消失。角色名前綴灌水 + 0.75 門檻時「紅莉栖喜歡貓。」跟
    「紅莉栖喜歡狗。」ratio 0.857，貓會被狗蓋掉。"""
    lines = [f"{NAME}{fact}" for fact in _FACTS]
    for i, new_line in enumerate(lines):
        existing = "\n".join(line for j, line in enumerate(lines) if j != i)
        merged = merge_self_memory(existing, new_line, character_name=NAME)
        for other in lines:
            assert other in merged.splitlines(), (
                f"插入「{new_line}」之後「{other}」不見了：{merged}"
            )


def test_character_name_prefix_does_not_inflate_similarity():
    existing = f"{NAME}喜歡貓。"
    incoming = f"{NAME}喜歡狗。"
    merged = merge_self_memory(existing, incoming, character_name=NAME)
    assert merged.splitlines() == [existing, incoming]


def test_one_word_difference_in_a_longer_line_is_still_two_entries():
    existing = f"{NAME}：最近迷上手沖咖啡。"
    incoming = f"{NAME}：最近迷上手沖紅茶。"
    merged = merge_self_memory(existing, incoming, character_name=NAME)
    assert merged.splitlines() == [existing, incoming]


def test_a_real_rewording_is_still_one_entry():
    existing = f"{NAME}：喜歡喝咖啡。"
    incoming = f"{NAME}：很喜歡喝咖啡。"
    merged = merge_self_memory(existing, incoming, character_name=NAME)
    assert merged == incoming


def test_short_lines_are_never_treated_as_similar():
    """剝掉前綴後任一方不到 6 字：短句判不出來，一律當成不同條。"""
    existing = f"{NAME}：怕蟑螂。"
    incoming = f"{NAME}：怕蜘蛛。"
    merged = merge_self_memory(existing, incoming, character_name=NAME)
    assert merged.splitlines() == [existing, incoming]


def test_identical_short_lines_are_still_deduplicated():
    """短句不比相似度，但一模一樣的行永遠不重複。"""
    existing = f"{NAME}：怕蟑螂。"
    merged = merge_self_memory(existing, existing, character_name=NAME)
    assert merged == existing


def test_incoming_lines_are_deduplicated_against_each_other():
    """同一輪模型吐出兩條講同一件事的行，只留後者。"""
    incoming = f"{NAME}：喜歡喝咖啡。\n{NAME}：很喜歡喝咖啡。"
    merged = merge_self_memory("", incoming, character_name=NAME)
    assert merged == f"{NAME}：很喜歡喝咖啡。"


def test_incoming_dedup_keeps_distinct_lines():
    incoming = f"{NAME}：喜歡喝咖啡。\n{NAME}：討厭夏天。"
    merged = merge_self_memory("", incoming, character_name=NAME)
    assert merged == incoming
