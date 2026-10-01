"""舊 conf.yaml 開機時升級一次。

upgrade_codes 那一套只在 git pull 升級時跑，而且會把 Tomoshibi 自己的鍵當成多餘的
刪掉，所以不用它。這裡逐行改：註解、排版、其他設定原樣。每一步都先確認還沒做過，
跑第二次不會再改任何東西。
"""

from __future__ import annotations

import re

from loguru import logger

from .conf_editor import (
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
