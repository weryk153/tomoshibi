"""中文 think_tag 提示詞測試。

原本的 think_tag_prompt.txt 全文為英文、範例是 *lowers head*，導致 LLM
產生英文動作描述跑到字幕上，這是它當初被停用的原因。這個測試守住
「不得含英文動作範例」這個回歸。
"""

import re

import yaml

from prompts import prompt_loader

PROMPT_NAME = "think_tag_prompt_zh"


def test_prompt_is_loadable():
    content = prompt_loader.load_util(PROMPT_NAME)
    assert content.strip()


def test_prompt_teaches_the_think_tag():
    content = prompt_loader.load_util(PROMPT_NAME)
    assert "<think>" in content
    assert "</think>" in content


def test_positive_examples_have_no_english_actions():
    """正面範例中星號包覆的動作描述不得含 ASCII 字母。

    這是 think_tag_prompt 當初被停用的根因：英文範例讓 LLM 模仿出英文動作
    描述並跑到字幕上。檢查只涵蓋「錯誤範例」之前的內容——標示為不要模仿的
    反面範例本來就需要示範錯誤寫法（例如把情緒關鍵字寫成 *smirk*）。
    """
    content = prompt_loader.load_util(PROMPT_NAME)
    positive = content.split("範例（錯誤")[0]
    starred = re.findall(r"\*[^*]+\*", positive)
    assert starred, "提示詞必須至少含一個星號動作範例，否則 LLM 學不到格式"
    for fragment in starred:
        assert not re.search(r"[A-Za-z]", fragment), f"含英文動作範例：{fragment}"


def test_prompt_forbids_actions_outside_the_tag():
    """觀察到 qwen3.5 會把動作寫在標籤外並混進台詞中間，提示詞必須明文禁止。"""
    content = prompt_loader.load_util(PROMPT_NAME)
    assert "不可以出現星號" in content
    assert "範例（錯誤" in content


def test_template_enables_the_zh_prompt():
    with open("config_templates/conf.tomoshibi.default.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tool_prompts = config["system_config"]["tool_prompts"]
    assert tool_prompts["think_tag_prompt"] == PROMPT_NAME


def test_the_prompt_does_not_break_its_own_asterisk_rule():
    """規則 2 說「標籤外絕對不可以出現星號」，提示詞自己就不能用 **粗體**。

    這不是潔癖：提示詞裡的每個星號都是在示範用法，而 markdown 的 `**` 會示範
    一種規則明文禁止的寫法。（順帶一提，先前加說明時就是在這裡踩到，被
    test_positive_examples_have_no_english_actions 擋下來的。）
    """
    content = prompt_loader.load_util(PROMPT_NAME)
    assert "**" not in content, "提示詞裡不該有 markdown 粗體——它違反自己的規則 2"
