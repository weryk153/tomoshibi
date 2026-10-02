"""寫進設定檔、但要重新載入才生效的變更清單。

設定抽屜頂端那條「有 N 項變更還沒生效」讀這份清單。記在記憶體：重新整理頁面
還在；重新載入或換角色成功（兩者都會重讀 conf.yaml 與角色檔）就清空；後端重開
本來就全部生效，所以也是空的。
"""

from __future__ import annotations

_pending: list[str] = []


def mark(key: str) -> None:
    if key not in _pending:
        _pending.append(key)


def pending() -> list[str]:
    return list(_pending)


def clear() -> None:
    _pending.clear()
