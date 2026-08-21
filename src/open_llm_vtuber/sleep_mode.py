"""睡眠勿擾：使用者說「晚安」之後，她不再主動開口；下一句真的話就喚醒。

她照樣回應你主動的發話——被關掉的只有 proactive speak 那條路
（conversation_handler 在觸發前問 is_sleeping）。

整條規則都在這個模組裡：呼叫端對每一句真人輸入呼叫 note_user_message，
要主動開口前呼叫 is_sleeping，不需要知道「晚安」怎麼判斷、喚醒的條件是什麼。

狀態是 chat_history/<conf_uid>/ 底下的旗標檔（存在＝睡著）。這是行為需求而不是
實作偷懶：晚安之後 server 重啟，她不該又開始搭話。

更早的版本用的旗標檔叫 .quiet_mode；讀取時一併
承認它，喚醒時一併清掉，已經說過晚安的使用者升級後不會突然被搭話。
"""

import os

from loguru import logger

from .utils.path_safety import safe_join

_FLAG_NAME = ".sleep_mode"
_LEGACY_FLAG_NAME = ".quiet_mode"

# 進入睡眠的訊號。子字串比對：「好啦我要去睡了，晚安。」也算。
_GOODNIGHT = "晚安"


def _flag_path(conf_uid: str) -> str:
    return safe_join("chat_history", conf_uid, _FLAG_NAME)


def _legacy_flag_path(conf_uid: str) -> str:
    return safe_join("chat_history", conf_uid, _LEGACY_FLAG_NAME)


def is_sleeping(conf_uid: str) -> bool:
    """現在是不是晚安～下一句話之間。主動開口前先問這個。"""
    try:
        return os.path.isfile(_flag_path(conf_uid)) or os.path.isfile(
            _legacy_flag_path(conf_uid)
        )
    except Exception:
        # 檔案系統出錯時寧可讓她說話，也不要永遠沉默。
        return False


def note_user_message(conf_uid: str, text: str) -> None:
    """餵進一句「真人」的輸入，模組自己決定睡或醒。

    只餵真人說的話——主動觸發的提示不是使用者在講話，餵進來會把她自己的
    開場白當成喚醒訊號。

    規則：
    - 含「晚安」→ 睡。就算已經睡了也維持睡（再說一次晚安不算醒來）。
    - 其他非空訊息、而且正在睡 → 醒。不必特地說早安。
    - 空白訊息不算數：ASR 偶爾送出空白或純標點的結果，那不是使用者醒了。
    """
    try:
        if not isinstance(text, str) or not text.strip():
            return

        if _GOODNIGHT in text:
            _fall_asleep(conf_uid)
        elif is_sleeping(conf_uid):
            _wake_up(conf_uid)
    except Exception as e:
        logger.warning(f"[sleep_mode] state change failed for {conf_uid}: {e}")


def _fall_asleep(conf_uid: str) -> None:
    p = _flag_path(conf_uid)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("sleeping\n")
    logger.info(f"[sleep_mode] 晚安——暫停主動說話 for {conf_uid}")


def _wake_up(conf_uid: str) -> None:
    for p in (_flag_path(conf_uid), _legacy_flag_path(conf_uid)):
        if os.path.isfile(p):
            os.remove(p)
    logger.info(f"[sleep_mode] 醒了——恢復主動說話 for {conf_uid}")
