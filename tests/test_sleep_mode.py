"""睡眠勿擾（sleep_mode）：說晚安之後她不再主動開口，你下一句話就喚醒。

早期版本（quiet_mode.py）只提供 set/get，
「晚安」偵測與「下一句喚醒」的規則散在 single_conversation 的呼叫端；重寫版
把整條規則收進模組，呼叫端只剩「餵訊息」與「問現在能不能主動說話」兩件事。

狀態存旗標檔（存在＝睡著），重啟後仍保留——這是行為需求，不是實作細節：
晚安之後 server 重啟，她不該又開始搭話。
"""

import os

from src.open_llm_vtuber.sleep_mode import (
    is_sleeping,
    note_user_message,
    _flag_path,
    _legacy_flag_path,
)

CONF = "sleep-mode-test"


def _cleanup() -> None:
    for p in (_flag_path(CONF), _legacy_flag_path(CONF)):
        if os.path.isfile(p):
            os.remove(p)


def setup_function() -> None:
    _cleanup()


def teardown_function() -> None:
    _cleanup()


def test_goodnight_puts_her_to_sleep():
    note_user_message(CONF, "晚安")

    assert is_sleeping(CONF) is True


def test_goodnight_inside_a_sentence_counts():
    note_user_message(CONF, "好啦我要去睡了，晚安。")

    assert is_sleeping(CONF) is True


def test_the_next_real_message_wakes_her():
    # 不必特地說早安——醒來後的第一句話就是訊號。
    note_user_message(CONF, "晚安")
    note_user_message(CONF, "早")

    assert is_sleeping(CONF) is False


def test_blank_input_does_not_wake_her():
    # ASR 偶爾會送出空白或純標點的辨識結果，那不是「使用者醒了」。
    note_user_message(CONF, "晚安")
    note_user_message(CONF, "   ")
    note_user_message(CONF, "")

    assert is_sleeping(CONF) is True


def test_saying_goodnight_again_stays_asleep():
    # 已經睡了又說一次晚安，不能被「非晚安即喚醒」的規則誤判成醒來。
    note_user_message(CONF, "晚安")
    note_user_message(CONF, "晚安晚安")

    assert is_sleeping(CONF) is True


def test_survives_restart_via_the_flag_file():
    # 狀態在檔案系統上；模組沒有記憶體狀態可失去，這裡釘住的是「檔案存在＝睡著」。
    note_user_message(CONF, "晚安")

    assert os.path.isfile(_flag_path(CONF))


def test_legacy_quiet_mode_flag_still_counts_as_sleeping():
    # 舊版（quiet_mode.py）的旗標檔叫 .quiet_mode。已經說過晚安的使用者升級後
    # 不該突然被搭話。
    p = _legacy_flag_path(CONF)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("quiet")

    assert is_sleeping(CONF) is True

    # 而且下一句話要能喚醒（把舊旗標一併清掉）。
    note_user_message(CONF, "醒了")
    assert is_sleeping(CONF) is False
