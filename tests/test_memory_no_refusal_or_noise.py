"""核心記憶不該記「她做不到」與聽不清楚的那一輪。

實際發生過的事：使用者說「1-80 隨便選 5 個號碼」，芙莉蓮回「我沒辦法幫你挑」。
那句拒絕被整理進 core_memory.md：

    使用者希望芙莉蓮幫忙選號碼，但芙莉蓮表示無法做到，因為抽獎號碼通常是隨機
    或自行決定，她連碰都碰不到。

這行之後每一輪都被注入系統提示，於是變成一個閉環：她拒絕一次 → 記憶把「她做
不到」寫成事實 → 下一輪提示告訴她做不到 → 她再拒絕，而且逐字照抄。使用者連問
四次，拿到四次一模一樣的回覆。

同一個機制也讓「芙莉蓮明確表示不想談論性相關話題」在檔案裡重複了四行。

第二類雜訊是語音辨識失敗的回合。53 行的記憶裡有 7 行是「使用者進行測試，確認
聲音傳導正常」這種東西，9 行是拒絕或聽不懂——三成的篇幅在記沒有價值的事，還
把上限（1500 字）吃掉，逼整理去刪掉真正該留的。

規則 2「關於角色自己的：說過的計畫、表明過的立場」是入口：拒絕會被歸成「立場」。
"""

from src.open_llm_vtuber.memory_core import build_consolidation_prompt


def _prompt(user_input: str, ai_response: str) -> str:
    return build_consolidation_prompt(
        current="",
        user_input=user_input,
        ai_response=ai_response,
        cap=1500,
        character_name="芙莉蓮",
    )


def test_forbids_recording_the_character_declining_something():
    prompt = _prompt("隨便選五個號碼", "我沒辦法幫你挑。")

    assert "拒絕" in prompt
    assert "做不到" in prompt


def test_forbids_recording_turns_that_were_not_understood():
    prompt = _prompt("嘅風采。", "剛才那句話好像沒連得上。")

    assert "聽不" in prompt


def test_forbids_recording_connectivity_and_audio_checks():
    # 這一輪本身不可以出現「測試」兩個字，否則它會從對話原文漏進提示詞，
    # 測試就變成在驗證回音而不是規則。
    prompt = _prompt("喂，聽得到嗎", "聽得到。")

    assert "測試" in prompt


def test_still_records_the_character_own_plans():
    # 收窄第二類的範圍不能把它整條砍掉——角色說過的計畫本來就該記，那是上一次
    # 修正（test_memory_prompt_subject）的重點，不能倒退。
    prompt = _prompt("去哪", "我可能跟著他們往北走。")

    assert "芙莉蓮" in prompt
    assert "主詞" in prompt
