"""舊 agent（basic_memory_agent）留下的記憶檔，只在引擎第一次用到時讀一次。

她記得什麼現在全由 AI Character Engine 負責。這裡只剩讀舊檔的函式，給
character_engine_agent 把它們搬進引擎：

- chat_history/<conf_uid>/<history_uid>/core_memory.md：一段對話的記憶。
- chat_history/<conf_uid>/self_memory.md：她自己說過的事，所有對話共用。

舊的 core_memory.md 兩種主詞混在一起，classify_memory_lines 把她自己的那幾行分出來。
"""

import re
from pathlib import Path

from loguru import logger

from .utils.path_safety import safe_join


def _memory_file(conf_uid: str, history_uid: str) -> Path:
    """記憶檔位置。

    conf_uid 與 history_uid 都是請求可控的。分兩段呼叫 safe_join——先把 conf_uid
    關進 chat_history/，再把 history_uid 關進 chat_history/<conf_uid>/——是刻意的：
    一次呼叫 safe_join("chat_history", conf_uid, history_uid, ...) 只保證結果留在
    chat_history/ 之內，history_uid 帶 "../" 仍能跳出 conf_uid 自己的資料夾、
    寫進另一個角色的目錄，因為那個位置一樣落在 chat_history/ 底下、擋不住。
    分段之後，history_uid 的逃逸目標就是 conf_uid 自己那層，才擋得住。

    呼叫端必須先確定 history_uid 非空——記憶屬於一段對話，沒有對話就沒有記憶。
    """
    char_dir = safe_join("chat_history", conf_uid)
    return Path(safe_join(char_dir, history_uid, "core_memory.md"))


def load_core_memory(conf_uid: str, history_uid: str) -> str:
    """讀出這段對話的記憶；沒有、或讀不到，一律回空字串。

    這條在注入路徑上，絕不能丟例外——檔案系統的問題不可以炸掉對話。

    history_uid 為空（連線還在初始化）時回空字串，不要退回舊的角色層路徑：
    那會變成「有時候讀這裡、有時候讀那裡」。
    """
    if not history_uid:
        return ""
    try:
        f = _memory_file(conf_uid, history_uid)
        return f.read_text(encoding="utf-8").strip() if f.is_file() else ""
    except Exception as e:
        logger.warning(f"[core_memory] load failed for {conf_uid}/{history_uid}: {e}")
        return ""


def _self_memory_file(conf_uid: str) -> Path:
    """chat_history/<conf_uid>/self_memory.md。

    放角色層、不在任何一段對話底下：刪對話不動它，開新對話也讀得到。
    conf_uid 是請求可控的，過 safe_join。
    """
    return Path(safe_join("chat_history", conf_uid, "self_memory.md"))


def read_self_memory(conf_uid: str) -> str:
    """讀不到就丟例外。要拿它當合併起點的人得知道「空」是真的空還是讀不到。"""
    f = _self_memory_file(conf_uid)
    return f.read_text(encoding="utf-8").strip() if f.is_file() else ""


# 第二人稱一律代表「這行在講對方」。「妳」是女性寫法、「您」是敬語，模型對
# 不同使用者會整份換一種寫法——只擋「你」的話，「紅莉栖答應妳下次帶書來。」
# 會被判成她自己的事實，跟對方有關的承諾寫進所有對話共用的角色層檔案。
# 刻意不含「他」「她」：她講第三者、或用第三人稱講自己（「紅莉栖說她小時候
# 住在美國」）時會誤殺整行。
_SELF_FORBIDDEN = ("對方", "你", "妳", "您")


_PARENTHETICAL_ONLY = re.compile(r"^（[^）]*）$")


_LIST_PREFIXES = ("- ", "• ", "・ ", "* ")


# 模型也會自己編號。沒剝掉的話整行不以角色名開頭，全部掉進對話記憶。
# 最多三位數、後面一定要接空白——「2024.11 開始學畫。」曾經被當成「2024.」
# 這個編號前綴吃掉，剩下「11 開始學畫。」；年份後面接的是數字不是空白，
# 加上這兩條限制就不會再中招（真的編號列表模型也一律會接空白）。
_NUMBERED_PREFIX = re.compile(r"^\d{1,3}[.、)] ")


def _strip_list_prefix(line: str) -> str:
    for prefix in _LIST_PREFIXES:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return _NUMBERED_PREFIX.sub("", line, count=1).strip()


def classify_memory_lines(text: str, character_name: str) -> tuple[str, str]:
    """把整理 LLM 輸出的單一清單逐行分成 (對話記憶, 她自己的)。

    分類由程式做、不靠模型：9B 模型在三輪實測裡做不到穩定的兩段輸出。
    規則（每行先 strip、去掉開頭的條列符號或數字編號）：
    - 純括號行（^（[^）]*）$）丟掉——模型會把提示詞裡的說明文字照抄回來。
    - 以角色名開頭、且整行不含「對方」「你」「妳」「您」→ 她自己的。
    - 其餘（以「對方」開頭、主詞不明、或提到對方）→ 對話記憶。分不清的一律留在
      對話記憶——那一邊是私人的，放錯不會外洩。
    角色名為空時，沒有任何行會被判成她自己的（並記一筆 warning：那等於整個 self
    分類失效，是設定錯誤，不可以無聲發生）。
    """
    who = (character_name or "").strip()
    if not who:
        logger.warning(
            "[self_memory] classify called without a character_name; "
            "every line will stay in the conversation memory"
        )
    conv_lines: list[str] = []
    self_lines: list[str] = []
    for raw_line in (text or "").splitlines():
        line = _strip_list_prefix(raw_line.strip())
        if not line or _PARENTHETICAL_ONLY.match(line):
            continue
        if (
            who
            and line.startswith(who)
            and not any(tok in line for tok in _SELF_FORBIDDEN)
        ):
            self_lines.append(line)
        else:
            conv_lines.append(line)
    return "\n".join(conv_lines), "\n".join(self_lines)
