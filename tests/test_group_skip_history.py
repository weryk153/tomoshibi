"""群組對話要不要把這一輪寫進歷史。

group_conversation 存 AI 回覆的那段寫成了 for-else：

    for member_uid in group_members:
        store_message(...)
    else:
        logger.debug("Skipping storing AI response to history (proactive speak)")

`else` 是掛在 for 上的（Python 的 for-else），迴圈正常跑完就會執行。所以它一邊
存、一邊印「跳過存檔」，而真正該有的 skip_history 判斷整個不見了——單人對話的
主動發言不會寫進歷史，群組模式卻會。

判斷本身在單人與群組兩邊是同一個表達式，抽成一個函式才有地方測，也才不會再各
寫一份。
"""

from src.open_llm_vtuber.conversations.conversation_utils import should_skip_history


def test_metadata_says_skip():
    assert should_skip_history({"skip_history": True}) is True


def test_metadata_says_do_not_skip():
    assert should_skip_history({"skip_history": False}) is False


def test_no_metadata_at_all():
    # 一般的使用者發話沒有 metadata，那當然要存。
    assert should_skip_history(None) is False


def test_empty_metadata():
    assert should_skip_history({}) is False


def test_always_returns_a_bool():
    # 原本的寫法 `metadata and metadata.get(...)` 在 metadata 是 None 時回傳
    # None 而不是 False。用在 if 判斷沒差，但拿去比對或序列化就會出事。
    assert should_skip_history(None) is False
    assert isinstance(should_skip_history(None), bool)
    assert isinstance(should_skip_history({"skip_history": "yes"}), bool)
