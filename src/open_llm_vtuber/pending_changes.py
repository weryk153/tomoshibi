"""寫進設定檔、但要重新載入才生效的變更清單。

設定抽屜頂端那條「有 N 項變更還沒生效」讀這份清單。記在記憶體：重新整理頁面
還在；重新載入或換角色成功（兩者都會重讀 conf.yaml 與角色檔）就清空；後端重開
本來就全部生效，所以也是空的。

要重啟後端才生效的（RESTART_KEYS，例如綁定位址）重新載入不會清：重新載入不會
改它，後端重開時這份清單本來就是空的。
"""

from __future__ import annotations

# 重新載入不會生效、要重啟後端的。綁定位址（host）是啟動時決定的。
RESTART_KEYS = frozenset({"host"})

_pending: list[str] = []


def mark(key: str) -> None:
    if key not in _pending:
        _pending.append(key)


def unmark(key: str) -> None:
    if key in _pending:
        _pending.remove(key)


def pending() -> list[str]:
    return list(_pending)


def needs_restart() -> bool:
    return any(key in RESTART_KEYS for key in _pending)


def clear() -> None:
    """重新載入或換角色成功時呼叫：只清那些重新載入就生效的。"""
    _pending[:] = [key for key in _pending if key in RESTART_KEYS]
