"""一次性搬移:角色層的 core_memory.md → 該角色 active 對話底下。

記憶改成每段對話一份之後,舊的 chat_history/<角色>/core_memory.md 不會再被任何
程式碼讀到。不搬的話,使用者下次連上她就失憶了,而且沒有任何錯誤訊息。

搬過去的目標是 active_history_store 記的那段對話——那正是 websocket_handler
還原時讀的同一個值,所以搬完下次連上就會被讀到。
"""

import os
from pathlib import Path

from loguru import logger

from .active_history_store import get_active_history_uid

_ROOT = "chat_history"
_NAME = "core_memory.md"
_KEPT = "core_memory.md.pre-split"


def migrate_character_memories() -> list:
    """回傳實際搬移過的 conf_uid 清單。任何失敗都只記 warning,不擋開機。"""
    moved = []
    root = Path(_ROOT)
    if not root.is_dir():
        return moved

    for char_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        old = char_dir / _NAME
        if not old.is_file():
            continue

        conf_uid = char_dir.name
        history_uid = get_active_history_uid(conf_uid)
        if not history_uid:
            # 不存在、壞掉、不安全都會回 None。憑空建立一段對話會產生使用者
            # 從來沒開過的對話,而且記憶被塞在裡面。
            logger.info(f"[memory-migration] {conf_uid} 沒有 active 對話,跳過")
            continue

        dest = char_dir / history_uid / _NAME
        if dest.exists():
            logger.info(f"[memory-migration] {conf_uid}/{history_uid} 已有記憶,跳過")
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = old.read_text(encoding="utf-8")
            # 原子寫入:先寫暫存檔再 os.replace。半路死掉的話 dest 要嘛不存在、
            # 要嘛是完整內容,不會出現「內容被截斷但 dest.exists() 是 True」
            # 這種以後永遠被當成「已搬移」跳過、內容卻是壞的情況。
            tmp = dest.with_name(f".{dest.name}.tmp")
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, dest)
            # 原檔改名保留而不是刪除:搬錯了還救得回來。
            old.rename(char_dir / _KEPT)
            moved.append(conf_uid)
            logger.info(f"[memory-migration] {conf_uid} → {history_uid}")
        except (OSError, UnicodeDecodeError) as e:
            # UnicodeDecodeError 是 ValueError 的子類,不是 OSError——壞掉、
            # 非 UTF-8 的舊檔會從這裡冒出來。要一起接住,否則一個字元角色
            # 的舊記憶檔壞掉,就會讓例外飛出這次迴圈,連帶跳過排序在它後面
            # 的所有角色,而外層 run_server.py 的 bare except 又會把這個
            # 錯誤悄悄吞掉,變成每次開機都重演同樣的沉默失敗。
            logger.warning(
                f"[memory-migration] {conf_uid} 搬移失敗({type(e).__name__}: {e})"
            )

    return moved
