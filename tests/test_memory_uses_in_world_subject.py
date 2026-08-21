"""記憶不用「使用者」當主詞——那是系統的詞，不是角色的詞。

人設裡沒有「使用者」這個概念，它一貫用「對方」（出現 11 次），而且明文禁止角色
主動提起 AI、程式、資料、系統、電腦這類詞。「使用者」是同一個語域的詞，卻被記憶
放在幾乎每一行的開頭，每一輪都注入系統提示。

已經漏出去過：紅莉栖說過「我當然知道你是使用者，或者更直白一點，就是來找我對話
的人……你是出現在『現在』這個世界線裡、能自由與我交談的物件」。

不能直接改用「你」——系統提示是寫給角色看的，那裡的「你」指的是角色自己，主詞
會整個混掉。「對方」既不是系統詞，也不會跟角色搞混，而且人設本來就在用。
"""

from src.open_llm_vtuber.memory_core import build_consolidation_prompt


def _prompt() -> str:
    return build_consolidation_prompt(
        # 這輪的原文一個「對方」都不能有，否則它會從對話內容漏進提示詞，
        # 測試就變成在驗證回音而不是規則。
        current="喜歡安靜的氛圍。",
        user_input="今天很累",
        ai_response="辛苦了。",
        cap=1500,
        character_name="芙莉蓮",
    )


def test_the_subject_label_is_the_in_world_word():
    # 釘住主詞規則那一句本身，不是「提示詞裡有沒有出現過對方」——後者太鬆，
    # 別條規則順手提到「對方」就會讓它通過。
    assert "「對方」或「芙莉蓮」開頭" in _prompt()


def test_the_system_word_is_gone_entirely():
    # 留一處都不行：模型會照著提示詞裡出現過的詞寫，記憶檔於是又長回「使用者」開頭。
    assert "使用者" not in _prompt()


def test_the_two_categories_survive_the_rename():
    # 換詞不能把上一輪修正（兩類、主詞、擋拒絕與雜訊）弄丟。
    prompt = _prompt()
    assert "主詞" in prompt
    assert "拒絕" in prompt
    assert "聽不" in prompt
    assert "測試" in prompt
