"""就地編輯 conf.yaml，不動使用者寫的註解與排版。

conf.yaml 是人手寫的檔案：註解、順序、空行、縮排都帶著作者的意圖。設定頁存一個
開關，不可以把整份讀成物件再重新序列化——那會把上面全部洗掉，使用者下次打開檔案
會發現自己寫的說明不見了。所以這裡走「找到那一行、只改那一行」的路。

四個層次，由下往上：

1. ``find_block_extent``  定位一個區塊（key 那一行，以及它縮排子項的範圍）
2. ``rewrite_*_leaf``     在範圍內就地改寫一個葉節點，保留縮排與行尾註解
3. ``upsert_leaf``        同上，但找不到就補一行進去
4. ``write_conf``         原子寫回，並保留一份使用者原始檔的備份

型別各有專用的寫入函式不是囉唆：YAML 的 ``True`` 與 ``'True'`` 是布林與字串兩件
事，寫錯型別 Pydantic 那關會炸。所以布林、整數、字串各走各的。

這些原語原本散在三個模組裡——translator_route 擁有區塊定位與字串寫入、
memory_route 擁有整數與 upsert、perf_route 跨模組向兩邊借。一個「翻譯」模組
擁有全域的設定檔編輯原語沒有道理，改設定的路徑也不該繞經它。契約由
tests/test_conf_editor.py 釘住。
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional

from loguru import logger

CONF_PATH = "conf.yaml"

# 行尾註解：至少一個空白之後的 # 開始，到行尾。
_TRAILING_COMMENT = re.compile(r"(\s+#.*?)\s*$")
# 區塊裡沒有任何子項可參考時，用兩格縮排。
_DEFAULT_INDENT = "  "


# --- 定位 --------------------------------------------------------------------

def find_block_extent(
    lines: list[str],
    key_pattern: re.Pattern,
    start_from: int = 0,
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """找出 ``key:`` 那一行，以及它底下縮排區塊的 [start, end) 範圍。

    回傳 (key 的行號, key 的縮排量, 區塊結束行號)；找不到回 (None, None, None)。

    區塊在「下一個縮排量小於等於 key 的非空非註解行」結束。中間的空行與註解算
    區塊的一部分——它們通常是在描述底下那些設定。
    """
    key_index = None
    key_indent = None
    for i in range(start_from, len(lines)):
        m = key_pattern.match(lines[i])
        if m:
            key_index = i
            key_indent = len(m.group(1))
            break

    if key_index is None:
        return None, None, None

    end = len(lines)
    for j in range(key_index + 1, len(lines)):
        line = lines[j]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip()) <= key_indent:
            end = j
            break
    return key_index, key_indent, end


def split_leaf(line: str) -> tuple[str, str]:
    """把一行拆成 (縮排, 行尾註解)，兩者都要原樣保留。

    公開的：偶爾需要改一個不在任何具名區塊裡的葉節點（例如全檔唯一的
    llm_provider），那時仍然要用同一套「保留縮排與註解」的規則。
    """
    indent = line[: len(line) - len(line.lstrip())]
    m = _TRAILING_COMMENT.search(line.rstrip("\n"))
    return indent, m.group(1) if m else ""


def _find_leaf(lines: list[str], start: int, end: int, key: str) -> Optional[int]:
    for j in range(start, end):
        if lines[j].lstrip().startswith(key + ":"):
            return j
    return None


# --- 改寫 --------------------------------------------------------------------

def _rewrite(lines: list[str], start: int, end: int, key: str, rendered: str) -> bool:
    index = _find_leaf(lines, start, end, key)
    if index is None:
        return False
    indent, comment = split_leaf(lines[index])
    lines[index] = f"{indent}{key}: {rendered}{comment}\n"
    return True


def rewrite_bool_leaf(lines: list[str], start: int, end: int, key: str, value: bool) -> bool:
    """改寫一個布林葉節點，寫成裸的 True／False。

    加引號會變成字串 'True'，Pydantic 讀進來就不是布林了。
    """
    return _rewrite(lines, start, end, key, str(bool(value)))


def rewrite_int_leaf(lines: list[str], start: int, end: int, key: str, value: int) -> bool:
    """改寫一個整數葉節點，寫成裸的數字（同理，不能加引號）。"""
    return _rewrite(lines, start, end, key, str(int(value)))


def rewrite_str_leaf(lines: list[str], start: int, end: int, key: str, value: str) -> bool:
    """改寫一個字串葉節點，加單引號並跳脫內部的單引號。"""
    escaped = str(value).replace("'", "''")
    return _rewrite(lines, start, end, key, f"'{escaped}'")


def _block_indent(lines: list[str], start: int, end: int) -> str:
    """看區塊裡既有的子項是怎麼縮排的，新插入的行跟著它。"""
    for j in range(start, end):
        line = lines[j]
        if line.strip() and not line.lstrip().startswith("#"):
            return line[: len(line) - len(line.lstrip())]
    return _DEFAULT_INDENT


def upsert_leaf(lines: list[str], start: int, end: int, key: str, rendered: str) -> int:
    """就地改寫葉節點；不存在就插一行進去。回傳區塊新的結束行號。

    UI 開得出來的設定就該存得下去。這些鍵有程式端的預設值，手寫的 conf.yaml 裡
    常常根本沒有那一行——早期版本在這種情況直接丟 KeyError，畫面顯示「無法寫入
    設定檔」，而使用者只是想存一個他有權存的值。

    插入位置是區塊尾端，但會往回跳過尾隨的空行與註解——那些通常是在介紹下一個
    段落，插在它們後面看起來會像是別人的東西。
    """
    index = _find_leaf(lines, start, end, key)
    if index is not None:
        indent, comment = split_leaf(lines[index])
        lines[index] = f"{indent}{key}: {rendered}{comment}\n"
        return end

    indent = _block_indent(lines, start, end)
    insert_at = end
    while insert_at > start and (
        not lines[insert_at - 1].strip()
        or lines[insert_at - 1].lstrip().startswith("#")
    ):
        insert_at -= 1

    lines.insert(insert_at, f"{indent}{key}: {rendered}\n")
    return end + 1


def block_extent(lines: list[str], key: str, start_from: int = 0) -> tuple[int, int]:
    """某個 ``key:`` 區塊底下子項的範圍。找不到就丟 KeyError。

    比 find_block_extent 好用的地方是它直接吃鍵名、而且找不到就丟——呼叫端不必
    每次自己寫一次 regex，也不會忘記檢查 None（忘了的話後面會拿 None 去切片，
    錯誤訊息跟真正的原因差十萬八千里）。
    """
    pattern = re.compile(rf"^(\s*){re.escape(key)}:\s*(#.*)?$")
    start, _, end = find_block_extent(lines, pattern, start_from)
    if start is None:
        raise KeyError(f"{key}: line not found in conf.yaml")
    return start + 1, end


def sub_block_extent(
    lines: list[str],
    parent_start: int,
    parent_end: int,
    key: str,
) -> tuple[Optional[int], Optional[int]]:
    """在 [parent_start, parent_end) 之內找一個具名子區塊；找不到回 (None, None)。

    限定範圍是安全性質，不是效率考量：同一個葉節點名字會出現在好幾個兄弟區塊
    底下（asr_config.azure_asr.api_key 與 tts_config.azure_tts.api_key 都叫
    api_key）。沒有限定範圍，改語音辨識的金鑰會寫進語音合成那塊——而且不會有
    任何徵兆。

    子區塊的結束位置也夾在父區塊之內，多一層保險。
    """
    pattern = re.compile(rf"^(\s*){re.escape(key)}:\s*(#.*)?$")
    start, _, end = find_block_extent(lines, pattern, parent_start)
    if start is None or start >= parent_end:
        return None, None
    return start + 1, min(end, parent_end)


def nested_extent(lines: list[str], *keys: str) -> tuple[int, int]:
    """沿著一條鍵的路徑一層一層鑽下去，回傳最內層區塊的範圍。

    ``nested_extent(lines, "agent_config", "llm_configs", "ollama_llm")`` 會逐層
    確認每一層都在上一層之內，任何一層找不到就丟 KeyError，訊息指出是哪一層。

    每層都要夾界的理由跟 sub_block_extent 一樣：同名的鍵在檔案別處也可能有，
    不夾就會鑽到別人家裡去改東西。
    """
    start, end = block_extent(lines, keys[0])
    for key in keys[1:]:
        inner_start, inner_end = sub_block_extent(lines, start, end, key)
        if inner_start is None:
            raise KeyError(f"{key}: not found inside {keys[keys.index(key) - 1]}")
        start, end = inner_start, inner_end
    return start, end


def system_config_extent(lines: list[str]) -> tuple[int, int]:
    """``system_config`` 底下子項的範圍。"""
    return block_extent(lines, "system_config")


def character_config_extent(lines: list[str]) -> tuple[int, int]:
    """``character_config`` 底下子項的範圍。找不到那個區塊就丟 KeyError。"""
    return block_extent(lines, "character_config")


# --- 讀寫 --------------------------------------------------------------------

def read_conf_lines() -> list[str]:
    """整份讀成行，保留換行符。

    用 open(newline="") 而不是 Path.read_text：後者在 Python 3.10 沒有 newline
    參數（3.13 才加），預設的 universal newlines 會把 CRLF 讀成 LF，寫回去就
    整份翻掉。newline="" 關掉翻譯，位元組原樣進出。
    """
    with open(CONF_PATH, "r", encoding="utf-8", newline="") as f:
        return f.read().splitlines(keepends=True)


def _backup_once() -> None:
    """留一份使用者原始 conf.yaml 的備份，只留第一次。

    只備份一次是刻意的：備份的價值在於「我們動手之前那一份」。每次寫入都覆蓋的話，
    第二次存檔就把它變成了我們自己寫過的版本，等於沒有備份。
    """
    backup = CONF_PATH + ".bak"
    if os.path.exists(backup):
        return
    try:
        shutil.copy2(CONF_PATH, backup)
    except Exception as e:
        logger.warning(f"[conf] could not create conf.yaml.bak: {type(e).__name__}")


def write_conf_document(dump) -> None:
    """原子寫回一份 ruamel 文件物件，第一次寫入前先備份。

    write_conf 收的是行，這個收的是「怎麼把文件寫出去」的函式（``dump(f)``）。
    有些改動用整份 round-trip 物件表達比逐行改自然得多——例如把多行人設寫成
    literal block scalar——但備份與原子寫入的規則兩邊必須一樣，所以共用同一條路。
    """
    _backup_once()
    path = Path(CONF_PATH)
    tmp = path.with_name(f".{path.name}.tmp")
    # newline="" 的理由見 read_conf_lines。
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        dump(f)
    os.replace(tmp, path)


def write_conf(lines: list[str]) -> None:
    """原子寫回 conf.yaml，第一次寫入前先備份。

    設定檔寫到一半被中斷，下次開機就起不來——所以先寫暫存檔再 os.replace。
    """
    _backup_once()
    path = Path(CONF_PATH)
    tmp = path.with_name(f".{path.name}.tmp")
    # newline="" 的理由見 read_conf_lines。Path.write_text 在 3.10 有這個參數。
    tmp.write_text("".join(lines), encoding="utf-8", newline="")
    os.replace(tmp, path)
