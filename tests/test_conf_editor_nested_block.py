"""在一個區塊裡就地寫入巢狀子區塊（用途：extra_body）。

三種起始狀態要分開釘：
- 子區塊已經存在 → 就地 upsert 葉節點，不重複建立
- 完全不存在 → 建立子區塊與葉節點
- 只存在被註解掉的版本（樣板就長這樣）→ 視同不存在，且不得動到那段註解

第三條是這個功能最容易寫錯的地方。sub_block_extent 的 regex 是
`^(\\s*)key:\\s*(#.*)?$`，`# extra_body:` 的 # 卡在空白與 key 之間，不會誤中——
這份測試就是要把那個保證釘住，因為它是靠 regex 的細節成立的。
"""

from src.open_llm_vtuber.conf_editor import (
    nested_extent,
    sub_block_extent,
    upsert_nested_block,
)

EXISTING = """character_config:
  agent_config:
    llm_configs:
      lmstudio_llm:
        base_url: 'http://127.0.0.1:1234/v1'
        model: 'old-model'
        extra_body:
          reasoning_effort: 'low'
""".splitlines(keepends=True)

ABSENT = """character_config:
  agent_config:
    llm_configs:
      lmstudio_llm:
        base_url: 'http://127.0.0.1:1234/v1'
        model: 'old-model'
""".splitlines(keepends=True)

COMMENTED = """character_config:
  agent_config:
    llm_configs:
      lmstudio_llm:
        base_url: 'http://127.0.0.1:1234/v1'
        model: 'old-model'
        # 若你載入的是推理／思考型模型，加上這段關掉它的推理。
        # extra_body:
        #   reasoning_effort: 'none'
""".splitlines(keepends=True)


def _block(lines):
    return nested_extent(
        lines, "character_config", "agent_config", "llm_configs", "lmstudio_llm"
    )


def test_updates_an_existing_nested_block():
    lines = list(EXISTING)
    start, end = _block(lines)
    upsert_nested_block(lines, start, end, "extra_body", {"reasoning_effort": "'none'"})
    text = "".join(lines)
    assert "reasoning_effort: 'none'" in text
    assert "reasoning_effort: 'low'" not in text
    assert text.count("extra_body:") == 1, "重複建立了子區塊"


def test_creates_the_block_when_absent():
    lines = list(ABSENT)
    start, end = _block(lines)
    upsert_nested_block(lines, start, end, "extra_body", {"reasoning_effort": "'none'"})
    text = "".join(lines)
    assert "extra_body:" in text
    assert "reasoning_effort: 'none'" in text
    # 縮排要比父層深一層，否則 YAML 結構是錯的
    assert "\n          reasoning_effort: 'none'\n" in text


def test_commented_example_counts_as_absent_and_is_left_alone():
    lines = list(COMMENTED)
    start, end = _block(lines)
    upsert_nested_block(lines, start, end, "extra_body", {"reasoning_effort": "'none'"})
    text = "".join(lines)
    # 註解原封不動
    assert "# extra_body:" in text
    assert "#   reasoning_effort: 'none'" in text
    # 真正的區塊被建立了（未被註解的那一個）
    real = [ln for ln in lines if ln.strip() == "extra_body:"]
    assert len(real) == 1, "沒有建立真正的 extra_body 區塊，或建了兩個"


def test_multiple_leaves_all_land():
    lines = list(ABSENT)
    start, end = _block(lines)
    upsert_nested_block(
        lines, start, end, "extra_body", {"reasoning_effort": "'none'", "foo": "'bar'"}
    )
    text = "".join(lines)
    assert "reasoning_effort: 'none'" in text
    assert "foo: 'bar'" in text


def test_returned_end_lets_a_second_call_work():
    """回傳值要跟 upsert_leaf 一樣是新的區塊結束行號，否則連續寫入會錯位。"""
    lines = list(ABSENT)
    start, end = _block(lines)
    end = upsert_nested_block(lines, start, end, "extra_body", {"a": "'1'"})
    upsert_nested_block(lines, start, end, "extra_body", {"b": "'2'"})
    text = "".join(lines)
    assert text.count("extra_body:") == 1
    assert "a: '1'" in text and "b: '2'" in text


def test_sub_block_extent_ignores_commented_keys():
    """upsert_nested_block 的正確性靠這個保證，直接釘住它。"""
    lines = list(COMMENTED)
    start, end = _block(lines)
    assert sub_block_extent(lines, start, end, "extra_body") == (None, None)
