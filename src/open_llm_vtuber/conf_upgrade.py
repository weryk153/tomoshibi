"""舊 conf.yaml 開機時升級一次。

upgrade_codes 那一套只在 git pull 升級時跑，而且會把 Tomoshibi 自己的鍵當成多餘的
刪掉，所以不用它。這裡逐行改：註解、排版、其他設定原樣。每一步都先確認還沒做過，
跑第二次不會再改任何東西。
"""

from __future__ import annotations

import os
import re

from loguru import logger

from .conf_editor import (
    CONF_PATH,
    block_extent,
    read_conf_lines,
    rewrite_str_leaf,
    sub_block_extent,
    write_conf,
)

# 舊 agent 專屬、引擎 agent 不讀的 character_config 葉節點。
RETIRED_LEAVES = ("core_memory_max_chars", "memory_consolidation_interval")


def upgrade_conf_lines(lines: list[str]) -> list[str]:
    """就地改寫；回傳改了什麼（給 log 看），沒改就是空清單。"""
    changes: list[str] = []
    try:
        agent_start, agent_end = block_extent(lines, "agent_config")
    except KeyError:
        return changes

    for i in range(agent_start, agent_end):
        if re.match(
            r"^\s*conversation_agent_choice:\s*['\"]?basic_memory_agent['\"]?",
            lines[i],
        ):
            rewrite_str_leaf(
                lines,
                agent_start,
                agent_end,
                "conversation_agent_choice",
                "character_engine_agent",
            )
            changes.append(
                "conversation_agent_choice: basic_memory_agent → character_engine_agent"
            )
            break

    settings_start, settings_end = sub_block_extent(
        lines, agent_start, agent_end, "agent_settings"
    )
    if settings_start is not None:
        has_new = any(
            re.match(r"^\s*conversation:\s*(#.*)?$", lines[i].rstrip("\n"))
            for i in range(settings_start, settings_end)
        )
        for i in range(settings_start, settings_end):
            m = re.match(
                r"^(\s*)basic_memory_agent:(\s*(#.*)?)$", lines[i].rstrip("\n")
            )
            if m and not has_new:
                newline = "\n" if lines[i].endswith("\n") else ""
                lines[i] = f"{m.group(1)}conversation:{m.group(2)}{newline}"
                changes.append(
                    "agent_settings.basic_memory_agent → agent_settings.conversation"
                )
                break

    try:
        cc_start, cc_end = block_extent(lines, "character_config")
    except KeyError:
        return changes
    for key in RETIRED_LEAVES:
        for i in range(cc_start, cc_end):
            # 只動 character_config 的直接子項（兩格縮排）。
            if re.match(rf"^  {key}:", lines[i]):
                del lines[i]
                cc_end -= 1
                changes.append(f"拿掉 character_config.{key}（舊 agent 專屬）")
                break
    return changes


def upgrade_conf_file() -> list[str]:
    """讀 conf.yaml、升級、有改才寫回（write_conf 第一次寫入前會留 conf.yaml.bak）。"""
    lines = read_conf_lines()
    changes = upgrade_conf_lines(lines)
    if changes:
        write_conf(lines)
        for change in changes:
            logger.info(f"[conf] upgraded: {change}")
    return changes


def own_everything(cc: dict, base_cc: dict, player_language: str) -> list[str]:
    from .character_settings import DEFAULTS, OWNED, _dig, _set

    added = []
    for name, path in OWNED.items():
        if _dig(cc, path) is not None:
            continue
        value = _dig(base_cc, path)
        if value is None and name == "reply_language":
            value = player_language or None
        if value is None:
            value = DEFAULTS.get(name)
        if value is None:
            continue
        _set(cc, path, value)
        added.append(name)
    return added


def upgrade_character_data(
    data: dict, base_cc: dict, player_language: str
) -> list[str]:
    cc = data.get("character_config")
    if not isinstance(cc, dict):
        return []
    changes = []
    if "asr_config" in cc:
        del cc["asr_config"]
        changes.append("拿掉 asr_config（語音辨識屬於你的麥克風，只在模型頁設定）")
    agent = cc.get("agent_config")
    if isinstance(agent, dict) and "conversation_agent_choice" in agent:
        del agent["conversation_agent_choice"]
        changes.append("拿掉 agent_config.conversation_agent_choice")
        if not agent:
            del cc["agent_config"]
    added = own_everything(cc, base_cc, player_language)
    if added:
        changes.append("補上這個角色自己的 " + "、".join(added))
    return changes


def upgrade_character_files(directory: str = "characters") -> dict[str, list[str]]:
    from .api_guard import make_yaml
    from .character_settings import _load

    try:
        base = _load(CONF_PATH)
    except Exception as e:
        logger.warning(f"[conf] 讀不到 conf.yaml，角色檔不升級：{type(e).__name__}")
        return {}
    base_cc = base.get("character_config") or {}
    player_language = str(
        (base.get("system_config") or {}).get("player_language") or ""
    )
    yaml = make_yaml()
    yaml.allow_unicode = True
    results: dict[str, list[str]] = {}

    if "reply_language" not in base_cc and player_language:
        from .character_settings import write

        base_cc["reply_language"] = player_language
        # 逐行插入：conf.yaml 滿是註解，整份重寫會把下一段的標題註解黏過來。
        write("conf.yaml", {"reply_language": player_language})
        results["conf.yaml"] = ["補上底稿角色的 reply_language"]
        logger.info("[conf] upgraded conf.yaml: 補上底稿角色的 reply_language")

    if not os.path.isdir(directory):
        return results
    for root, _, names in os.walk(directory):
        for name in sorted(names):
            if not name.endswith(".yaml") or name.startswith("."):
                continue
            path = os.path.join(root, name)
            try:
                data = _load(path)
                if not isinstance(data, dict):
                    raise ValueError("not a mapping")
            except Exception as e:
                logger.warning(f"[conf] 跳過讀不了的角色檔 {path}：{type(e).__name__}")
                continue
            changes = upgrade_character_data(data, base_cc, player_language)
            if not changes:
                continue
            tmp = os.path.join(root, "." + name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.dump(data, f)
            os.replace(tmp, path)
            results[name] = changes
            for change in changes:
                logger.info(f"[conf] upgraded characters/{name}: {change}")
    return results
