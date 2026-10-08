"""角色擁有的設定：寫在那個角色自己的檔案裡。

底稿角色的檔案是 conf.yaml 的 character_config；其他角色是 characters/<檔名>。
一律用 round-trip 改那幾個鍵，註解與其他欄位原樣留著。
"""

from __future__ import annotations

import os
from typing import Any, Optional

from .api_guard import make_yaml
from .conf_editor import CONF_PATH

OWNED: dict[str, tuple[str, ...]] = {
    "tts_model": ("tts_config", "tts_model"),
    "voice": ("tts_config", "edge_tts", "voice"),
    "voice_lang": ("tts_config", "gpt_sovits_tts", "text_lang"),
    "ref_audio_path": ("tts_config", "gpt_sovits_tts", "ref_audio_path"),
    "prompt_text": ("tts_config", "gpt_sovits_tts", "prompt_text"),
    "prompt_lang": ("tts_config", "gpt_sovits_tts", "prompt_lang"),
    "reply_language": ("reply_language",),
    "translate_subtitle": (
        "tts_preprocessor_config",
        "translator_config",
        "translate_subtitle",
    ),
    "long_term_memory_enabled": ("long_term_memory_enabled",),
    "actions_enabled": ("actions_enabled",),
    "bilingual_subtitle": ("bilingual_subtitle",),
    "translation_audit": ("translation_audit",),
    "expression_source": ("expression_source",),
    "proactive_when_unanswered": ("proactive_when_unanswered",),
}
TOGGLES = (
    "translate_subtitle",
    "long_term_memory_enabled",
    "actions_enabled",
    "bilingual_subtitle",
    "translation_audit",
)
DEFAULTS: dict[str, Any] = {
    "translate_subtitle": False,
    "bilingual_subtitle": False,
    "translation_audit": False,
    "long_term_memory_enabled": True,
    "actions_enabled": False,
    "expression_source": "tags",
    "proactive_when_unanswered": "keep_talking",
}
# 角色頁設定端點收的選項（值只能是其中之一）；開關（TOGGLES）是 true／false。
CHOICES: dict[str, tuple[str, ...]] = {
    "expression_source": ("tags", "background"),
    "proactive_when_unanswered": ("keep_talking", "wait"),
}
SETTINGS = (*TOGGLES, *CHOICES)


def file_for(filename: str) -> Optional[str]:
    from .character_route import _safe_character_path

    if filename == "conf.yaml":
        return CONF_PATH
    path = _safe_character_path(filename)
    return path if path and os.path.isfile(path) else None


def filename_for_uid(conf_uid: str) -> Optional[str]:
    from .character_route import _conf_uid_of, _list_character_files

    if _conf_uid_of(CONF_PATH) == conf_uid:
        return "conf.yaml"
    for path in _list_character_files():
        if _conf_uid_of(path) == conf_uid:
            return os.path.basename(path)
    return None


def _load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return make_yaml().load(f) or {}


def _dig(node: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def effective(filename: str) -> dict[str, Any]:
    base = (_load(CONF_PATH).get("character_config")) or {}
    own: dict = {}
    if filename != "conf.yaml":
        path = file_for(filename)
        own = ((_load(path).get("character_config")) or {}) if path else {}
    values = {}
    for name, path in OWNED.items():
        value = _dig(own, path)
        if value is None:
            value = _dig(base, path)
        values[name] = DEFAULTS.get(name, "") if value is None else value
    return values


def _set(node: dict, path: tuple[str, ...], value: Any) -> None:
    for key in path[:-1]:
        if not isinstance(node.get(key), dict):
            node[key] = {}
        node = node[key]
    node[path[-1]] = value


def _render(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _write_conf_lines(changes: dict[str, Any]) -> None:
    """conf.yaml 逐行改：只動（或插入）那幾行，註解與 True／False 的寫法原樣留著。

    整份 round-trip 重寫會把下一段的標題註解黏到新插入的欄位上，還會把整個檔案的
    True 改寫成 true——那是使用者滿是註解的主設定。
    """
    from .conf_editor import (
        character_config_extent,
        nested_extent,
        read_conf_lines,
        upsert_leaf,
        upsert_nested_block,
        write_conf,
    )

    lines = read_conf_lines()
    for name, value in changes.items():
        path = OWNED[name]
        parent, leaf = path[:-1], path[-1]
        try:
            if parent:
                start, end = nested_extent(lines, "character_config", *parent)
            else:
                start, end = character_config_extent(lines)
            upsert_leaf(lines, start, end, leaf, _render(value))
        except KeyError:
            if not parent:
                raise
            try:
                # 只少最後一層（例如沒有 translator_config）：補在上一層底下。
                start, end = nested_extent(lines, "character_config", *parent[:-1])
            except KeyError:
                # 少不只一層：很少見，退回整份 round-trip（註解位置可能會動，但值對）。
                return _write_document(CONF_PATH, changes, is_conf=True)
            upsert_nested_block(lines, start, end, parent[-1], {leaf: _render(value)})
    write_conf(lines)


def write(filename: str, changes: dict[str, Any]) -> None:
    path = file_for(filename)
    if path is None:
        raise FileNotFoundError(filename)
    if filename == "conf.yaml":
        _write_conf_lines(changes)
        return
    _write_document(path, changes, is_conf=False)


def _write_document(path: str, changes: dict[str, Any], *, is_conf: bool) -> None:
    from .conf_editor import write_conf_document

    yaml = make_yaml()
    yaml.allow_unicode = True
    data = _load(path)
    cc = data.setdefault("character_config", {})
    for name, value in changes.items():
        _set(cc, OWNED[name], value)
    if is_conf:
        write_conf_document(lambda f: yaml.dump(data, f))
        return
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    os.replace(tmp, path)


# ---------------------------------------------------------------- 名詞與口頭禪
#
# 翻譯審核的建議（translate/audit.py）一筆一筆加進角色設定。這兩個是對照表，
# 不在 OWNED 裡：開機升級不替角色補，角色頁表單也不寫，只有這裡會加。
TERMS = ("protected_names", "catchphrases")


def terms(filename: str) -> dict[str, dict]:
    """角色實際用的 protected_names／catchphrases（自己沒有就是底稿的）。"""
    base = (_load(CONF_PATH).get("character_config")) or {}
    own: dict = base
    if filename != "conf.yaml":
        path = file_for(filename)
        own = ((_load(path).get("character_config")) or {}) if path else {}
    values = {}
    for name in TERMS:
        value = own.get(name)
        if not isinstance(value, dict):
            value = base.get(name)
        values[name] = dict(value) if isinstance(value, dict) else {}
    return values


def add_term(filename: str, kind: str, source: str, target: str) -> None:
    """加一筆：口頭禪是「來源 → 目標寫法」；名字是正確寫法底下多一個錯誤寫法。

    角色檔用 round-trip 就地改；底稿角色（conf.yaml）逐行改，只動那一筆
    （_write_conf_term）。角色自己還沒有這張表時，先抄一份底稿的再加（跟開機
    升級「她有自己的一份」同一條規則）。
    """
    if kind not in TERMS:
        raise ValueError(kind)
    path = file_for(filename)
    if path is None:
        raise FileNotFoundError(filename)
    yaml = make_yaml()
    yaml.allow_unicode = True
    data = _load(path)
    cc = data.setdefault("character_config", {})
    table = cc.get(kind)
    if not isinstance(table, dict):
        cc[kind] = table = terms(filename)[kind]
    if kind == "catchphrases":
        table[source] = target
    else:
        wrongs = table.get(target)
        if not isinstance(wrongs, list):
            table[target] = wrongs = []
        if source not in wrongs:
            wrongs.append(source)
    if filename == "conf.yaml":
        key = source if kind == "catchphrases" else target
        _write_conf_term(kind, key, table, table[key])
        return
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    os.replace(tmp, path)


def _quoted(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _term_line(key: str, value: Any) -> str:
    if isinstance(value, list):
        return f"{_quoted(key)}: [{', '.join(_quoted(v) for v in value)}]"
    return f"{_quoted(key)}: {_quoted(value)}"


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _entry_key(line: str) -> Any:
    """一行 ``key: ...`` 的鍵（照 YAML 讀，引號寫法不同也認得）；不是就 None。"""
    import yaml as pyyaml

    try:
        parsed = pyyaml.safe_load(line.strip())
    except Exception:
        return None
    if isinstance(parsed, dict) and len(parsed) == 1:
        return next(iter(parsed))
    return None


def _write_conf_term(kind: str, key: str, table: dict, value: Any) -> None:
    """conf.yaml 逐行改：只換（或插入）那一筆，其他行一個位元組都不動。

    整份 round-trip 會把 True 改寫成 true、搬動註解（見 _write_conf_lines）。
    那一筆原本是多行（區塊序列）時換成一行 flow 寫法；整張表寫成一行
    （``catchphrases: {...}``）時，只把那一行換成區塊。
    """
    from .conf_editor import (
        _block_indent,
        character_config_extent,
        read_conf_lines,
        sub_block_extent,
        upsert_nested_block,
        write_conf,
    )

    lines = read_conf_lines()
    start, end = character_config_extent(lines)
    newline = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    child = _block_indent(lines, start, end)
    inline = next(
        (
            i
            for i in range(start, end)
            if _indent(lines[i]) == len(child)
            and lines[i].lstrip().startswith(kind + ":")
            and lines[i].split(":", 1)[1].split("#", 1)[0].strip()
        ),
        None,
    )
    if inline is not None:
        inner = child + "  "
        lines[inline : inline + 1] = [f"{child}{kind}:{newline}"] + [
            f"{inner}{_term_line(k, v)}{newline}" for k, v in table.items()
        ]
        write_conf(lines)
        return
    inner_start, inner_end = sub_block_extent(lines, start, end, kind)
    if inner_start is None:
        upsert_nested_block(
            lines,
            start,
            end,
            kind,
            {_quoted(key): _term_line(key, value).split(": ", 1)[1]},
        )
        write_conf(lines)
        return
    inner = _block_indent(lines, inner_start, inner_end)
    rendered = f"{inner}{_term_line(key, value)}{newline}"
    for i in range(inner_start, inner_end):
        line = lines[i]
        if _indent(line) != len(inner) or line.lstrip().startswith(("#", "-")):
            continue
        if _entry_key(line) != key:
            continue
        # 這一筆的範圍：到下一個同層的鍵或更淺的行為止（PyYAML 的序列項目跟鍵
        # 同一層縮排，以 "- " 開頭，也算這一筆）。
        stop = i + 1
        while stop < inner_end:
            nxt = lines[stop]
            if nxt.strip() and not nxt.lstrip().startswith("#"):
                if _indent(nxt) < len(inner) or (
                    _indent(nxt) == len(inner) and not nxt.lstrip().startswith("-")
                ):
                    break
            stop += 1
        while stop > i + 1 and (
            not lines[stop - 1].strip() or lines[stop - 1].lstrip().startswith("#")
        ):
            stop -= 1
        lines[i:stop] = [rendered]
        write_conf(lines)
        return
    insert_at = inner_end
    while insert_at > inner_start and (
        not lines[insert_at - 1].strip()
        or lines[insert_at - 1].lstrip().startswith("#")
    ):
        insert_at -= 1
    lines.insert(insert_at, rendered)
    write_conf(lines)
