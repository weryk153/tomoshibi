"""core memory 儲存層的特徵測試。

寫在重寫之前、在舊實作上跑綠——它們釘的是行為契約，不是實作：

- 讀不到就回空字串，永不丟例外（注入路徑不能因為檔案問題炸掉對話）。
- 清空是截斷不是刪檔（house rule 不硬刪）。
- 手動儲存超過上限「照存但警告」，不偷偷截斷使用者打的字。
- 上限與整理頻率的夾界規則：壞值一律 fail-soft 回預設，垃圾設定不能讓
  整理悄悄停掉。

記憶現在是每段對話一份，所以每個呼叫都要帶 history_uid；HISTORY 是這份測試
固定用的那一段對話。
"""

import os

from src.open_llm_vtuber.memory_core import (
    CAP_CHARS,
    CAP_MAX,
    CAP_MIN,
    CONSOLIDATE_INTERVAL_DEFAULT,
    _clamp_cap,
    _clamp_interval,
    clear_core_memory,
    core_memory_path,
    load_core_memory,
    save_core_memory,
)

CONF = "memory-store-test"
HISTORY = "conv-1"


def _cleanup() -> None:
    p = core_memory_path(CONF, HISTORY)
    if os.path.isfile(p):
        os.remove(p)


def setup_function() -> None:
    _cleanup()


def teardown_function() -> None:
    _cleanup()


def test_load_returns_empty_when_nothing_saved():
    assert load_core_memory(CONF, HISTORY) == ""


def test_save_then_load_roundtrip():
    assert save_core_memory(CONF, HISTORY, "對方喜歡安靜。\n") is True
    assert load_core_memory(CONF, HISTORY) == "對方喜歡安靜。"


def test_clear_truncates_instead_of_deleting():
    save_core_memory(CONF, HISTORY, "要被忘掉的內容")

    assert clear_core_memory(CONF, HISTORY) is True
    assert load_core_memory(CONF, HISTORY) == ""
    # 檔案還在——清空是截斷不是刪檔。
    assert os.path.isfile(core_memory_path(CONF, HISTORY))


def test_clear_on_missing_file_counts_as_cleared():
    assert clear_core_memory(CONF, HISTORY) is True


def test_manual_save_over_cap_is_stored_verbatim():
    # 使用者在記憶分頁明確打的字要照存；偷偷截斷比超長更意外。
    long_text = "很長的記憶。" * 500  # 遠超 1500

    assert save_core_memory(CONF, HISTORY, long_text, cap=CAP_CHARS) is True
    assert load_core_memory(CONF, HISTORY) == long_text.strip()


def test_save_none_means_empty():
    save_core_memory(CONF, HISTORY, "舊內容")
    save_core_memory(CONF, HISTORY, None)

    assert load_core_memory(CONF, HISTORY) == ""


def test_cap_coercion_fails_soft():
    assert _clamp_cap(None) == CAP_CHARS
    assert _clamp_cap("garbage") == CAP_CHARS
    assert _clamp_cap(10) == CAP_MIN
    assert _clamp_cap(999999) == CAP_MAX
    assert _clamp_cap(2000) == 2000


def test_interval_coercion_fails_soft():
    assert _clamp_interval(None) == CONSOLIDATE_INTERVAL_DEFAULT
    assert _clamp_interval("x") == CONSOLIDATE_INTERVAL_DEFAULT
    assert _clamp_interval(4) == CONSOLIDATE_INTERVAL_DEFAULT
    assert _clamp_interval(3) == 3
    assert _clamp_interval(5) == 5


def test_path_is_confined_to_chat_history():
    # conf_uid 是請求可控的；逃出 chat_history/ 必須被擋下。
    import pytest

    with pytest.raises(Exception):
        core_memory_path("../outside", HISTORY)


def test_empty_history_uid_means_no_memory():
    # history_uid 為空代表連線還在初始化，沒有對話就沒有記憶：讀回空字串、
    # 寫入一律被擋下，不能悄悄退回角色層的舊路徑。
    assert core_memory_path(CONF, "") == ""
    assert load_core_memory(CONF, "") == ""
    assert save_core_memory(CONF, "", "內容") is False
    assert clear_core_memory(CONF, "") is False
