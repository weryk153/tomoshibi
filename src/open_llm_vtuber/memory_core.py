"""角色的長期核心記憶：一份小而精的檔案，每輪對話後由 LLM 背景維護。

兩層式設計（core memory + consolidation，同 MemGPT / Generative Agents 一脈）：

- **注入**：construct_system_prompt 把 chat_history/<conf_uid>/<history_uid>/
  core_memory.md 的內容附在 persona 後面，每輪都帶著。記憶屬於一段對話，不是
  一個角色——新對話從空白開始。
- **整理**：每輪對話結束後背景呼叫 LLM（fire-and-forget，不阻塞對話），
  判斷這輪有沒有值得留下的新事實，有才改寫檔案。

整理用的提示詞（build_consolidation_prompt）是這個模組的靈魂——它決定記憶會
被記成什麼樣子，歷次修正的教訓都寫在它的 docstring 裡。

- **她自己的記憶**：chat_history/<conf_uid>/self_memory.md，角色層、所有對話共用、
  上限固定 800 字。整理只讓 LLM 輸出一份清單，分類由程式逐行做
  （classify_memory_lines）：以角色名開頭、不含「對方」「你」的歸她自己的，其餘
  留在對話記憶。9B 模型在三輪 5×5 實測裡做不到穩定的兩段輸出，才改成這樣。
  分類出來的 self 行不會整份覆寫檔案，而是用 merge_self_memory 合併進既有內容：
  9B 模型收到「現有記憶」後，輸出「更新後的完整記憶」時會把舊條目丟掉、只吐這一
  輪的內容（連舊提示詞都一樣），整份覆寫的話她自己的記憶永遠只剩最後一輪。
  見 MEMORY_SYSTEM_DESIGN.md 的「The character's own memory」一節。

行為契約由 tests/test_memory_store_behavior.py 釘住。
"""

import asyncio
import difflib
import re
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from .utils.path_safety import safe_join

# --- 大小與頻率的界限 --------------------------------------------------------

CAP_CHARS = 1500  # 記憶檔字數上限的預設值；撞上限時由整理 LLM 自行提煉合併
CAP_MIN = 500  # 低於這個記不住東西
CAP_MAX = 8000  # 高於這個每輪 token 暴增、整理更容易漏

CONSOLIDATE_INTERVAL_DEFAULT = 1  # 每幾輪整理一次；1 = 每輪
CONSOLIDATE_INTERVAL_CHOICES = (1, 3, 5)  # 弱機／本地模型可選 3 或 5 省呼叫


def _coerce_int(value: Any, fallback: int) -> int:
    """設定值是外部來的，什麼垃圾都可能出現；轉不成整數就回 fallback。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _clamp_cap(value: Any) -> int:
    """把字數上限夾進 [CAP_MIN, CAP_MAX]；壞值 fail-soft 回預設。

    fail-soft 是刻意的：垃圾設定值不可以讓整理悄悄停掉。
    """
    n = _coerce_int(value, CAP_CHARS)
    return min(max(n, CAP_MIN), CAP_MAX)


def _clamp_interval(value: Any) -> int:
    """整理頻率只允許 {1, 3, 5}；其他一律回 1（每輪整理，最保守）。"""
    n = _coerce_int(value, CONSOLIDATE_INTERVAL_DEFAULT)
    return n if n in CONSOLIDATE_INTERVAL_CHOICES else CONSOLIDATE_INTERVAL_DEFAULT


# --- 儲存 --------------------------------------------------------------------


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


def core_memory_path(conf_uid: str, history_uid: str) -> str:
    """給 route 層用的公開路徑查詢。沒有對話、或路徑不安全時回空字串。

    load/save/clear 三個都吞掉 safe_join 丟出的 ValueError、fail soft 回空字串
    或 False；這個原本沒跟——一個不安全的 conf_uid/history_uid 會讓例外直接炸
    出去。memory_route 的 GET /api/memory 就是這樣裸呼叫這個函式，於是三個姊妹
    函式都能優雅降級的錯誤輸入，這裡會把設定頁的記憶分頁弄成 500。跟手足一致，
    回空字串。
    """
    if not history_uid:
        return ""
    try:
        return str(_memory_file(conf_uid, history_uid))
    except ValueError as e:
        logger.warning(f"[core_memory] unsafe path for {conf_uid}/{history_uid}: {e}")
        return ""


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


def _write_memory(conf_uid: str, history_uid: str, text: str) -> None:
    f = _memory_file(conf_uid, history_uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def clear_core_memory(conf_uid: str, history_uid: str) -> bool:
    """忘掉這段對話的全部記憶。

    截斷成空檔而不是刪檔（house rule 不硬刪）；檔案不存在本來就等於已清空。
    """
    if not history_uid:
        return False
    try:
        if _memory_file(conf_uid, history_uid).is_file():
            _write_memory(conf_uid, history_uid, "")
            logger.info(f"[core_memory] cleared for {conf_uid}/{history_uid}")
        return True
    except Exception as e:
        logger.warning(f"[core_memory] clear failed for {conf_uid}/{history_uid}: {e}")
        return False


def save_core_memory(
    conf_uid: str, history_uid: str, content: str, cap: int = CAP_CHARS
) -> bool:
    """整份覆寫記憶（記憶分頁的手動編輯用）。

    超過上限採「照存但警告」：使用者明確打的字尊重原樣，偷偷截斷比超長更意外；
    下一輪整理本來就會把過長內容提煉回上限內。None 視為空字串。
    """
    if not history_uid:
        return False
    try:
        text = (content or "").strip()
        limit = _clamp_cap(cap)
        if len(text) > limit:
            logger.warning(
                f"[core_memory] manual save for {conf_uid}/{history_uid} exceeds cap "
                f"({len(text)} > {limit} chars); stored as-is, will be "
                "compacted on next consolidation"
            )
        _write_memory(conf_uid, history_uid, text)
        logger.info(
            f"[core_memory] manually saved for {conf_uid}/{history_uid} ({len(text)} chars)"
        )
        return True
    except Exception as e:
        logger.warning(f"[core_memory] save failed for {conf_uid}/{history_uid}: {e}")
        return False


# --- 她自己的記憶（角色層，所有對話共用）--------------------------------------

SELF_CAP_CHARS = 800  # 固定，不開放設定；她自己的事本來就比關於對方的少


def _self_memory_file(conf_uid: str) -> Path:
    """chat_history/<conf_uid>/self_memory.md。

    放角色層、不在任何一段對話底下：刪對話不動它，開新對話也讀得到。
    conf_uid 是請求可控的，過 safe_join。
    """
    return Path(safe_join("chat_history", conf_uid, "self_memory.md"))


def self_memory_path(conf_uid: str) -> str:
    """給 route 層用。路徑不安全時回空字串（跟 core_memory_path 一致）。"""
    try:
        return str(_self_memory_file(conf_uid))
    except ValueError as e:
        logger.warning(f"[self_memory] unsafe path for {conf_uid}: {e}")
        return ""


def read_self_memory(conf_uid: str) -> str:
    """讀不到就丟例外。要拿它當合併起點的人得知道「空」是真的空還是讀不到。"""
    f = _self_memory_file(conf_uid)
    return f.read_text(encoding="utf-8").strip() if f.is_file() else ""


def load_self_memory(conf_uid: str) -> str:
    """在注入路徑上，絕不丟例外。"""
    try:
        return read_self_memory(conf_uid)
    except Exception as e:
        logger.warning(f"[self_memory] load failed for {conf_uid}: {e}")
        return ""


def _write_self_memory(conf_uid: str, text: str) -> None:
    f = _self_memory_file(conf_uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def save_self_memory(conf_uid: str, content: str) -> bool:
    """整份覆寫（設定頁手動編輯用）。超過上限照存並警告。

    超長的內容不會被「提煉」回上限內：self 記憶的維護是程式端合併
    （merge_self_memory），不是讓模型重寫，所以下次合併只會從最舊的行往下淘汰
    到裝得下為止。
    """
    try:
        text = (content or "").strip()
        if len(text) > SELF_CAP_CHARS:
            logger.warning(
                f"[self_memory] manual save for {conf_uid} exceeds cap "
                f"({len(text)} > {SELF_CAP_CHARS} chars); stored as-is"
            )
        _write_self_memory(conf_uid, text)
        logger.info(f"[self_memory] manually saved for {conf_uid} ({len(text)} chars)")
        return True
    except Exception as e:
        logger.warning(f"[self_memory] save failed for {conf_uid}: {e}")
        return False


def clear_self_memory(conf_uid: str) -> bool:
    """截斷成空檔而不是刪檔；檔案不存在等於已清空。"""
    try:
        if _self_memory_file(conf_uid).is_file():
            _write_self_memory(conf_uid, "")
            logger.info(f"[self_memory] cleared for {conf_uid}")
        return True
    except Exception as e:
        logger.warning(f"[self_memory] clear failed for {conf_uid}: {e}")
        return False


# --- 整理輸出的分類（程式端做，不靠模型）---------------------------------------

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


# 0.85，不是 0.75：短句差一個字的 ratio 本來就高（n 字差一字 = (n-1)/n），
# 「喜歡貓。」vs「喜歡狗。」在舊門檻下 0.857 就足以讓貓被狗蓋掉。
_SIMILARITY_THRESHOLD = 0.85
# 剝掉前綴後短於這個長度的行不比相似度：一兩個字的差異在短句裡就是完全不同的
# 事實（貓／狗、咖啡／紅茶），ratio 判不出來。完全相同的行另外走等值捷徑。
_MIN_COMPARABLE_LEN = 6
# 開頭的角色名／代稱 + 分隔符去掉再比對，避免「紅莉栖：喜歡咖啡」跟「喜歡咖啡」
# 因為多了主詞前綴而被誤判成不像。有角色名時優先剝角色名（模型常寫成
# 「紅莉栖喜歡貓。」，中間沒有任何分隔符，這個形狀下面那條正規式抓不到，
# 名字就整段留在被比較的文字裡灌水）；沒有角色名時退回「開頭一小段非標點
# 文字 + 冒號或空白」這個形狀，12 字元夠涵蓋常見稱呼，不會誤砍句子中段。
_LEADING_LABEL = re.compile(r"^[^：: ]{1,12}[：: ]")
_LEADING_SEPARATOR = re.compile(r"^[：: ]+")


def _normalize_for_similarity(line: str, character_name: str = "") -> str:
    who = (character_name or "").strip()
    if who and line.startswith(who):
        return _LEADING_SEPARATOR.sub("", line[len(who) :]).strip()
    return _LEADING_LABEL.sub("", line)


def _lines_are_similar(a: str, b: str, character_name: str = "") -> float:
    na = _normalize_for_similarity(a, character_name)
    nb = _normalize_for_similarity(b, character_name)
    if na == nb:
        return 1.0
    if len(na) < _MIN_COMPARABLE_LEN or len(nb) < _MIN_COMPARABLE_LEN:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _dedupe_incoming(lines: list[str], character_name: str) -> list[str]:
    """同一輪裡兩條講同一件事的行只留後者（後者是模型最後的說法）。

    比對只看「這行後面」的行、逐一比對到門檻就丟，不是遞移的——A 像 B、
    B 像 C，不代表 A 像 C（ratio 是連續值，不是等價關係），這裡刻意不做
    遞移閉包，演算法本身不變。這裡只是把原本靜默丟棄的行記下來：丟掉的行
    以前完全沒有痕跡，事後沒辦法追查某條記憶為什麼沒進最終結果。
    """
    kept: list[str] = []
    for idx, line in enumerate(lines):
        superseded_by = next(
            (
                later
                for later in lines[idx + 1 :]
                if _lines_are_similar(line, later, character_name)
                >= _SIMILARITY_THRESHOLD
            ),
            None,
        )
        if superseded_by is not None:
            logger.info(
                f"[self_memory] dedupe dropped incoming line {line!r}; "
                f"superseded by later line {superseded_by!r} this round"
            )
            continue
        kept.append(line)
    return kept


def merge_self_memory(
    existing: str,
    incoming: str,
    cap: int = SELF_CAP_CHARS,
    character_name: str = "",
) -> str:
    """把這輪分類出來的 self 行合併進既有的 self 記憶（程式端做，不靠模型）。

    9B 模型被要求輸出「更新後的完整記憶」時，只要現有記憶不是空的，就會把舊
    條目丟掉、只吐這一輪的內容——換掉提示詞也一樣（見 fix-round-5-brief.md 的
    離線重跑）。所以她自己的記憶不能讓模型整份覆寫，改成程式端合併：
    - 既有的行全部保留、順序不變；新行接在後面。
    - 相近的行（用 difflib.SequenceMatcher ratio、去掉開頭的角色名／代稱再比對，
      避免主詞前綴影響相似度判斷）視為同一條，留新的那行、放在舊的位置——
      這樣「喜歡喝咖啡」換成「很喜歡喝咖啡，尤其黑咖啡」不會變成兩條。
      一條新行同時貼近兩條以上舊行時（同一件事的兩份舊紀錄），只有 ratio 最高
      的那條被取代、留在它原本的位置，其餘一樣貼近的舊行整條刪掉，不留下不會
      自癒的重複舊行。同一輪的新行之間也互相去重，只留後者。
    - 完全相同的行落在同一個分支（ratio 1.0），不會重複。
    - 合併後超過 cap 時：先從這輪的新行由前往後丟（最早的新行先丟）直到新行
      本身裝得下——單一新行就比 cap 長時那行必然被丟掉，記一筆 warning；再從
      「這輪沒被取代也不是新增」的舊行裡挑最舊（最前面）的丟，直到總長不超過。
      先修新行、後淘汰舊行是刻意的：反過來做的話，一條放不進去的巨大新行會先
      把舊記憶整份淘汰掉，最後那行自己還是被丟掉，等於白白清空了檔案。

    去掉開頭角色名／代稱的正規化不認得主詞是誰——呼叫端要先把不同主詞的行
    分開（classify_memory_lines 已經這樣做，只把「她自己的」那一半的行交進來），
    不然「對方喜歡咖啡」跟「紅莉栖喜歡咖啡」單看去掉前綴後的內文會被判成相似。
    """
    if not (incoming or "").strip():
        return existing

    existing_lines = [ln.strip() for ln in (existing or "").splitlines() if ln.strip()]
    incoming_lines = _dedupe_incoming(
        [ln.strip() for ln in incoming.splitlines() if ln.strip()], character_name
    )

    # 這輪的新行本身就超過 cap 時，從最早的新行開始丟——舊記憶還沒動到，丟完
    # 之後剩下的舊行仍有機會留在檔案裡。
    while incoming_lines and len("\n".join(incoming_lines)) > cap:
        dropped = incoming_lines.pop(0)
        logger.warning(
            f"[self_memory] this round's self lines exceed cap ({cap} chars); "
            f"dropping the oldest one ({len(dropped)} chars)"
        )
    if not incoming_lines:
        return existing

    # 每條新行找它最像的舊行（ratio 最高、>= 門檻）來取代；同一條新行若同時貼近
    # 多條舊行，其餘的舊行視為同一件事的重複記錄，直接刪掉——不然會留下一條
    # 沒被取代、也不會再被下一輪比對修正的殘留重複行。
    replace_at: dict[int, str] = {}
    remove_existing_idx: set[int] = set()
    used_incoming: set[int] = set()
    for inc_idx, inc_line in enumerate(incoming_lines):
        candidates: list[tuple[float, int]] = []
        for ex_idx, ex_line in enumerate(existing_lines):
            if ex_idx in replace_at or ex_idx in remove_existing_idx:
                continue  # 已經被這輪更早的新行取代／標記刪除，不再爭搶
            ratio = _lines_are_similar(ex_line, inc_line, character_name)
            if ratio >= _SIMILARITY_THRESHOLD:
                candidates.append((ratio, ex_idx))
        if not candidates:
            continue
        candidates.sort(key=lambda c: (-c[0], c[1]))
        _, best_idx = candidates[0]
        replace_at[best_idx] = inc_line
        used_incoming.add(inc_idx)
        for _, dup_idx in candidates[1:]:
            remove_existing_idx.add(dup_idx)

    # is_new 標出「這輪動過」的行（取代或新增）：cap 超出時這些行不能被擠掉。
    merged: list[str] = []
    is_new: list[bool] = []
    for ex_idx, ex_line in enumerate(existing_lines):
        if ex_idx in remove_existing_idx:
            continue
        if ex_idx in replace_at:
            merged.append(replace_at[ex_idx])
            is_new.append(True)
        else:
            merged.append(ex_line)
            is_new.append(False)
    for inc_idx, inc_line in enumerate(incoming_lines):
        if inc_idx not in used_incoming:
            merged.append(inc_line)
            is_new.append(True)

    def _joined() -> str:
        return "\n".join(merged)

    while len(_joined()) > cap:
        evictable = [i for i, new in enumerate(is_new) if not new]
        if not evictable:
            break  # 只剩這輪動過的行，而它們前面已經修到裝得下了
        idx = evictable[0]
        merged.pop(idx)
        is_new.pop(idx)

    return _joined()


# --- 整理（consolidation）----------------------------------------------------


def build_consolidation_prompt(
    current: str,
    user_input: str,
    ai_response: str,
    cap: int,
    character_name: str = "",
    current_self: str = "",
    self_cap: int = SELF_CAP_CHARS,
) -> str:
    """組出記憶整理用的提示詞。抽成純函式是為了測得到——這段文字決定了記憶會
    被記成什麼樣子，而它出錯時沒有任何徵兆，只會安靜地把錯的事實留在檔案裡。

    舊版把整份記憶框成「關於使用者的長期記憶」，同時要求記「重要事件或對話
    結論」。當結論出自角色自己時，這兩條互相打架：角色的事實沒有欄位可放，
    只能被塞進使用者的主詞。實際結果是芙莉蓮說「我可能就跟著他們往北走」
    之後，記憶寫成「使用者目前正計畫跟隨費倫與修塔爾克前往北方」。

    所以框架改成兩類，並要求每條都寫明主詞——不是再加一條禁令，因為禁令
    （「絕不記 AI 自己說的話」）本來就已經在了，沒有用。

    第二輪修正：第二類原本寫「說過的計畫、表明過的立場」，而「立場」正好是拒絕
    的入口。芙莉蓮說「我沒辦法幫你挑號碼」之後，記憶寫下「她連碰都碰不到」，
    這行從此每一輪都進系統提示——她拒絕一次就被自己的舊台詞釘住，之後逐字重複
    同一句拒絕。使用者連問四次，拿到四次一模一樣的回覆。

    同時擋掉兩類雜訊：聽不清楚的回合（語音辨識失敗，不是任何人的事實），以及
    「測試聲音有沒有通」。實測 53 行的記憶裡這兩類佔了三成，還把 1500 字的上限
    吃掉，逼整理去刪真正該留的東西。

    第三輪修正：主詞從「使用者」改成「對方」。人設裡沒有「使用者」這個概念，它
    一貫用「對方」，而且明文禁止角色主動提起 AI、程式、資料、系統這類詞——「使用
    者」是同一個語域的詞，卻被放在記憶幾乎每一行的開頭，每一輪都注入。已經漏出去
    過：角色說過「我當然知道你是使用者……你是出現在『現在』能自由
    與我交談的物件」。

    不能改用「你」：系統提示是寫給角色看的，那裡的「你」指角色自己，主詞會整個
    混掉。

    第四輪修正（2026-09-15，回退）：曾經改成讓模型自己輸出兩段——「關於角色自己
    的」與「對話記憶」各佔一段，分別存到 self_memory.md 與 core_memory.md。但這個
    設計在 9B 模型（qwen/qwen3.5-9b）上三輪 5×5 人讀對照全部失敗：自己段抽取率
    0/25 → 0/25 → 11/25，第三輪還出現幻覺自我事實（模型編出從未在對話裡出現過的
    設定）。於是退回單一清單輸出，分類改由程式逐行做（見 classify_memory_lines）：
    以角色名開頭、整行不含「對方」「你」的判為她自己的，其餘留在對話記憶，分不清
    的一律留在對話記憶——那一邊是私人的，放錯不會外洩。

    同一輪也拿掉了「現有記憶：」欄位空的時候墊底的佔位文字（如「（目前還沒有任何
    記憶）」）：三輪實測裡這段文字多次被模型原樣或近乎原樣回顯進輸出，而照抄回來
    的字串會被 `_acceptable_rewrite` 當成合法內容寫進檔案。改成欄位空的時候直接
    留空；程式端「整行只有全形括號的內容一律丟掉」（見 classify_memory_lines）
    保留當第二層保險，佔位文字就算被回顯也進不了任何一份記憶。
    """
    who = character_name.strip() or "角色"
    existing = "\n".join(part for part in (current_self, current) if part)
    return (
        f"你是這個 AI 角色的記憶管理員。角色的名字是「{who}」。\n"
        "根據下面這輪對話，維護一份「這段關係的長期記憶」。\n\n"
        "規則（嚴格遵守）：\n"
        "- 記兩類事情，兩類都要記：\n"
        "  1. 關於對方的：身分／職業／正在做的事、偏好與習慣、希望被怎麼稱呼、\n"
        "     他明確講過的重要事件。\n"
        f"  2. 關於{who}自己的：說過的計畫、答應過的事、講過的關於自己的來歷或喜好。\n"
        f"- 每一條都必須以「對方」或「{who}」開頭，寫明這件事是誰的。省略主詞不行。\n"
        f"- {who}講的話絕對不可以寫成對方的事實。分不清楚是誰的就整條不要記。\n"
        "- 絕不記：一次性閒聊、寒暄、問候、沒有新資訊的對話。\n"
        f"- 絕不記{who}做不到、不擅長、不會、沒辦法、拒絕、不想談、沒興趣的事。\n"
        "  這種句子寫進記憶之後，\n"
        f"  每一輪都會告訴{who}她做不到，她就照著再拒絕一次，而且逐字重複。\n"
        "  同理也不記她表達過的情緒反應（覺得無奈、感到困惑、有點不耐煩）。\n"
        "- 絕不記聽不清楚、聽錯、猜對方在講什麼的那一輪。那是語音辨識的雜訊，\n"
        "  不是關於任何人的事實。\n"
        "- 絕不記測試、確認聲音有沒有傳到、連線通不通這種操作性的對話。\n"
        "- 用簡短條列，每條一行，繁體中文，台灣用語。\n"
        "- 如果這輪對話沒有任何值得記的新資訊，就原封不動輸出現有記憶，一個字都不要改。\n"
        f"- 關於對方與你們之間的條目合計控制在 {cap} 字元內、"
        f"{who}自己的條目合計控制在 {self_cap} 字元內；\n"
        "  若超過，合併或提煉舊條目（保留最關鍵、刪掉過時細節）。\n\n"
        f"現有記憶：\n{existing}\n\n"
        f"這輪對話：\n對方說：{user_input}\n{who}回：{ai_response}\n\n"
        "請輸出「更新後的完整記憶內容」本身，不要任何解釋、前言或標題。"
    )


def _rewrite_rejection_reason(candidate: str, current: str, cap: int) -> str | None:
    """整理 LLM 的輸出不能落地的理由；能落地時回 None。

    - 空的：模型判斷這輪沒東西可記（或整個失敗），不動檔案。
    - 跟現有一模一樣：寫了也是白寫。
    - 超過 cap 的 1.5 倍：模型沒守住長度指示，寧可丟掉這輪也不要讓檔案
      失控膨脹——注入是每輪都付的成本。

    回「理由」而不是布林，是因為丟掉一輪整理是靜默的：提示詞跟這個門檻曾經
    互相矛盾（提示詞允許 cap + self_cap、這裡用 int(cap * 1.5) 拒收），而丟掉
    的那些輪沒有留下任何一行 log，只能靠人事後推敲為什麼記憶沒更新。
    """
    if not candidate:
        return "empty candidate"
    if candidate == current:
        return "unchanged from the stored memory"
    limit = int(cap * 1.5)
    if len(candidate) >= limit:
        return f"{len(candidate)} chars exceeds the 1.5x cap ({limit})"
    return None


def _acceptable_rewrite(candidate: str, current: str, cap: int) -> bool:
    """能不能落地。理由見 _rewrite_rejection_reason。"""
    return _rewrite_rejection_reason(candidate, current, cap) is None


async def _request_rewrite(
    base_url: str,
    model: str,
    prompt: str,
    api_key: str,
    extra_body: dict | None,
) -> str:
    """讓對話用的 LLM 產出「更新後的完整記憶」。回傳清乾淨的文字。

    - Authorization：api_key 非空且不是 'ollama' 佔位才帶（本機 Ollama 不吃 header）。
    - extra_body 原樣併入。漏掉它曾讓這個功能從未寫出任何記憶：conf 靠
      extra_body.reasoning_effort='none' 關掉 Qwen3.5 的思考模式，這條路徑沒抄到，
      每次整理都思考到超過 60 秒 timeout，然後被 fail-soft 靜默吞掉。
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "stream": False,
        **(extra_body or {}),
    }
    headers = (
        {"Authorization": f"Bearer {api_key}"}
        if api_key and api_key != "ollama"
        else None
    )
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        text = r.json()["choices"][0]["message"]["content"]
    # 模型偶爾把整份輸出包在反引號裡
    return str(text).strip().strip("`").strip()


# --- 併發（同一個角色一次只整理一份）--------------------------------------

_consolidation_locks: "OrderedDict[str, asyncio.Lock]" = OrderedDict()
_MAX_LOCKS = 64


def _consolidation_lock(conf_uid: str) -> asyncio.Lock:
    """同一個角色的整理必須排隊。

    整理是「讀出整份記憶 → 丟給 LLM 重寫 → 整份覆寫」，中間那步要花到 60 秒。
    沒有鎖的話，第 N 輪還在等 LLM、第 N+1 輪就開始了：兩邊各自讀到同一份舊記憶
    當底稿，各自整份寫回，後寫的贏——先寫那輪的新事實就這樣消失，而且不留痕跡
    （整條路徑是 fire-and-forget，失敗只記 warning）。本地慢模型加上
    memory_consolidation_interval=1 時這是搆得到的，不是理論風險。

    鎖要含蓋「讀」才有用：只鎖寫入的話兩邊依然是從同一份底稿長出來的。

    鎖以 conf_uid 為單位，不是 (conf_uid, history_uid)：self_memory.md 是同角色所有
    對話共用的，兩段對話同時整理會各自讀到同一份舊的 self 記憶當底稿、整份寫回，
    後寫的蓋掉先寫的新條目。代價是同角色開兩段對話時整理會排隊，可接受。
    """
    key = str(conf_uid)
    lock = _consolidation_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _consolidation_locks[key] = lock
    _consolidation_locks.move_to_end(key)

    # 長時間執行不該讓這張表無限長。只淘汰沒被持有的鎖——把還鎖著的鎖丟掉，
    # 等於讓下一輪拿到一把新鎖，併發保護就破了。
    excess = len(_consolidation_locks) - _MAX_LOCKS
    if excess > 0:
        stale = [k for k, v in _consolidation_locks.items() if not v.locked()]
        for old_key in stale[:excess]:
            _consolidation_locks.pop(old_key, None)
    return lock


async def consolidate_core_memory(
    conf_uid: str,
    history_uid: str,
    user_input: str,
    ai_response: str,
    base_url: str,
    model: str,
    cap: int = CAP_CHARS,
    api_key: str = "",
    extra_body: dict | None = None,
    character_name: str = "",
    reply_language: str = "",
    protected_names: "Mapping[str, Sequence[str]] | None" = None,
    conversation_half: bool = True,
    through: "Callable[[Callable[[], Awaitable[str]]], Awaitable[str]] | None" = None,
) -> None:
    """一輪對話結束後背景執行：值得記的才更新 core_memory.md。

    ``conversation_half=False``：對方的那一半不寫。給自己記得對方的 agent 用
    （character_engine_agent 的記憶在引擎裡）；她自己的那一半照舊合併。

    ``through``：模型呼叫交給它去做（character_engine_agent 的 ``aside``：等她
    講完、排在引擎的背景工作後面）。不給就直接打——那會跟她的回覆搶同一顆模型。

    fire-and-forget——任何失敗只記 warning，絕不影響對話本身。

    ``reply_language``／``protected_names``：整理用的 LLM 跟一般回覆用同一顆模型，
    會犯同一種錯——把專有名詞寫成同音字（「橋田至」寫成「杜拉比」）。一般回覆的
    正規化只套在顯示／TTS 這一次性輸出上；記憶不套的話，錯字會原樣寫進
    core_memory.md／self_memory.md，之後每一輪注入回系統提示，模型再學回去、
    越滾越錯。所以在丟給 classify_memory_lines **之前**先套一次
    normalize_output_language_variant——分類是逐行字串比對（角色名開頭），錯字
    沒折回來的話「杜拉比」那一行永遠對不上角色名開頭，會被誤判進對話記憶。
    兩個參數留空／None 時 normalize 本來就直接回傳原文，行為與不傳時一致。
    """
    try:
        if not history_uid:
            return
        if not user_input or not user_input.strip():
            return

        limit = _clamp_cap(cap)
        # 讀→重寫→寫回，整段持鎖。見 _consolidation_lock。
        async with _consolidation_lock(conf_uid):
            current = load_core_memory(conf_uid, history_uid)
            current_self = load_self_memory(conf_uid)
            prompt = build_consolidation_prompt(
                current=current,
                user_input=user_input,
                ai_response=ai_response,
                cap=limit,
                character_name=character_name,
                current_self=current_self,
                self_cap=SELF_CAP_CHARS,
            )
            if through is None:
                raw = await _request_rewrite(
                    base_url, model, prompt, api_key, extra_body
                )
            else:
                raw = await through(
                    lambda: _request_rewrite(
                        base_url, model, prompt, api_key, extra_body
                    )
                )
            # local import：conversation_quality 目前不匯入 memory_core，沒有循環
            # 匯入風險，但兩邊都用 local import 是既有慣例（見 service_context.py）。
            from .conversation_quality import normalize_output_language_variant

            raw = normalize_output_language_variant(
                raw, reply_language, protected_names
            )
            conv_candidate, self_candidate = classify_memory_lines(raw, character_name)
            rejected = _rewrite_rejection_reason(conv_candidate, current, limit)
            if not conversation_half:
                pass
            elif rejected is None:
                _write_memory(conf_uid, history_uid, conv_candidate)
                logger.info(
                    f"[core_memory] updated for {conf_uid}/{history_uid} "
                    f"({len(conv_candidate)} chars)"
                )
            else:
                logger.info(
                    f"[core_memory] conversation half not written for "
                    f"{conf_uid}/{history_uid}: {rejected}"
                )
            merged_self = merge_self_memory(
                current_self,
                self_candidate,
                SELF_CAP_CHARS,
                character_name=character_name,
            )
            if merged_self != current_self:
                _write_self_memory(conf_uid, merged_self)
                logger.info(
                    f"[self_memory] merged for {conf_uid} ({len(merged_self)} chars)"
                )
    except Exception as e:
        logger.warning(
            f"[core_memory] consolidate failed for {conf_uid}/{history_uid}: {e}"
        )


def resolve_consolidation_llm(character_config: Any) -> tuple[str, str, str, dict]:
    """Return the OpenAI-compatible endpoint used by the active conversation LLM.

    Memory consolidation is part of the active conversation pipeline, so it must
    follow ``basic_memory_agent.llm_provider`` instead of silently hard-coding the
    ``openai_compatible_llm`` block.  LM Studio, Ollama and the other compatible
    providers expose the same base_url/model/key leaves.
    """
    agent_config = character_config.agent_config
    provider = agent_config.agent_settings.basic_memory_agent.llm_provider
    llm_config = getattr(agent_config.llm_configs, provider, None)
    if llm_config is None:
        raise ValueError(f"Active LLM provider config not found: {provider}")

    base_url = str(getattr(llm_config, "base_url", "") or "").strip()
    model = str(getattr(llm_config, "model", "") or "").strip()
    api_key = str(getattr(llm_config, "llm_api_key", "") or "")
    if not base_url or not model:
        raise ValueError(
            f"Active LLM provider {provider} is not OpenAI-compatible for memory consolidation"
        )
    # extra_body 必須跟著走：對話快是因為它關掉思考模式，整理沒帶就會 timeout。
    extra_body = getattr(llm_config, "extra_body", None) or {}
    return base_url, model, api_key, dict(extra_body)
