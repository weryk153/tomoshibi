"""think_tag 提示詞不可以把情緒關鍵字一起擋在台詞之外。

實測：芙莉蓮的 313 則回覆裡，情緒關鍵字出現 0 次，送到前端的 expressions 欄位
從頭到尾都是空的——不是「很少看到其他表情」，是一次都沒有。11 個關鍵字確實有被
注入系統提示，extract_emotion 也正常。

原因是同一份系統提示裡兩條規則打架：

  live2d_expression_prompt（英文，先）：把 [joy] 這類標籤放進回覆裡，經常用。
  think_tag_prompt_zh 規則 2（中文，後）：「標籤之外只能有你說出口的話」。

[joy] 不是說出口的話。中文那段更長、更晚、而且註明「請嚴格遵守」，模型於是整批
不發。規則 4「情緒關鍵字要用方括號」補救不了——它在糾正「不要寫成星號」，沒有
給出「可以寫在台詞段落裡」的許可。

這裡釘住的是：規則 2 必須自己講明方括號關鍵字是例外。
"""

from pathlib import Path

PROMPT = Path("prompts/utils/think_tag_prompt_zh.txt")


def _rule_two() -> str:
    """規則 2 整條，含續行——例外寫在續行上，只讀第一行會漏掉。"""
    lines = PROMPT.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("2.")),
        None,
    )
    if start is None:
        raise AssertionError("think_tag_prompt_zh.txt 裡找不到規則 2")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("3.")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_rule_two_carves_out_the_bracket_keywords():
    # 「只能有說出口的話」這句話本身沒問題，問題是它沒有例外。例外必須寫在同一
    # 條規則裡；寫在別條（規則 4 就是）模型不會把它讀成對規則 2 的鬆綁。
    assert "方括號" in _rule_two()


def test_the_prompt_shows_a_keyword_inside_a_spoken_line():
    # 規則講了還不夠，正確範例裡必須真的有一句台詞帶著方括號關鍵字——這份提示詞
    # 的所有正確範例目前都不帶，模型照著範例學就永遠不會發。
    text = PROMPT.read_text(encoding="utf-8")
    head, _, tail = text.partition("範例（錯誤")
    assert "[" in head and "]" in head
    good_examples = [
        line
        for line in head.splitlines()
        if "[" in line
        and "]" in line
        and "規則" not in line
        and "關鍵字要用" not in line
    ]
    assert good_examples, "正確範例裡沒有任何一句帶方括號關鍵字的台詞"
