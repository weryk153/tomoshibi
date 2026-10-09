"""她每次回幾句：全部角色共用的設定（conf.yaml 的 system_config.reply_length）。

說話規則本來就寫「普通的回覆一到三句」，但本機 9B 常一次講 5–11 句。每句都要翻
譯、合成，一輪要 40–100 秒才合成完，下一輪就跟著排隊變慢。所以每一輪的備註再帶
一句「這次回覆最多幾句」——對照過（2026-10-09，三月）：加「最多三句」，三句裡兩
句明顯變短（117→38、139→57 字）。

存了馬上生效：每一輪讀一次，檔案沒改就用上次讀到的值。
"""

from __future__ import annotations

import os

from loguru import logger

from .conf_editor import CONF_PATH

NOTES = {
    "short": "這次回覆最多三句，短而直接。",
    "medium": "這次回覆最多五句。",
    "free": "",
}
DEFAULT = "short"

_cache: tuple[float, str] | None = None


def _read() -> str:
    from .config_manager.utils import read_yaml

    block = (read_yaml(CONF_PATH) or {}).get("system_config") or {}
    value = str(block.get("reply_length") or DEFAULT)
    return value if value in NOTES else DEFAULT


def current() -> str:
    global _cache
    try:
        mtime = os.path.getmtime(CONF_PATH)
    except OSError:
        return DEFAULT
    if _cache is None or _cache[0] != mtime:
        try:
            _cache = (mtime, _read())
        except Exception as e:  # noqa: BLE001 — 讀不到設定就用預設，不能讓這一輪失敗
            logger.warning(f"[reply-length] could not read conf: {type(e).__name__}")
            return DEFAULT
    return _cache[1]


def note() -> str:
    """這一輪備註要帶的那一句；「不限」是空字串。"""
    return NOTES[current()]
