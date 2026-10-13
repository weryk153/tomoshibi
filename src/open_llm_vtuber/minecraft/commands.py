"""把她的目標編成 Mindcraft 指令。

實測（2026-10-14）兩層模型都不可靠：她寫「chop a tree」，身體那邊的 Andy-4.2 翻成
`!attack("oak_log")`。Mindcraft 收到以 `!` 開頭的指令會直接執行、不經它的模型，所以
認得出來的目標在這裡編成指令；認不出來的才原句交給 Andy-4.2 猜。
一個目標可能是好幾步（木鎬要先木板、木棍），回一串，控制器等身體閒下來一步一步送。
"""

from __future__ import annotations

import math
import re

_NUM = r"(?:(?:a|an|some|the)\s+)?(?:(\d+)\s+)?"


def _n(match: re.Match, default: int) -> int:
    for group in match.groups():
        if group and group.isdigit():
            return int(group)
    return default


def compile_goal(goal: str) -> list[str]:
    """回要依序送的指令；編不出來就回原句（交給 Andy-4.2）。"""
    g = goal.strip().lower()
    rules: list[tuple[str, callable]] = [
        (
            rf"(?:collect|gather|get|chop|cut|punch)\s+{_NUM}(?:oak\s+)?(?:logs?|wood|trees?)",
            lambda m: [f'!collectBlocks("oak_log", {_n(m, 10)})'],
        ),
        (
            r"craft(?:\s+a|\s+an|\s+\d+)?\s+crafting\s+table",
            lambda m: [
                '!craftRecipe("oak_planks", 1)',
                '!craftRecipe("crafting_table", 1)',
            ],
        ),
        (
            r"craft(?:\s+a)?\s+wooden\s+pickaxe",
            lambda m: [
                '!craftRecipe("oak_planks", 2)',
                '!craftRecipe("stick", 1)',
                '!craftRecipe("wooden_pickaxe", 1)',
            ],
        ),
        (
            r"craft(?:\s+a)?\s+stone\s+pickaxe",
            lambda m: ['!craftRecipe("stick", 1)', '!craftRecipe("stone_pickaxe", 1)'],
        ),
        (
            r"craft(?:\s+a)?\s+(?:stone\s+)?(?:axe|sword)",
            lambda m: [
                '!craftRecipe("stick", 1)',
                f'!craftRecipe("{"stone_" if "stone" in g else "wooden_"}{"axe" if "axe" in g else "sword"}", 1)',
            ],
        ),
        (
            rf"(?:collect|mine|get|gather)\s+{_NUM}(?:cobblestone|stone)",
            lambda m: [f'!collectBlocks("stone", {_n(m, 8)})'],
        ),
        (
            rf"(?:collect|mine|get|gather)\s+{_NUM}coal",
            lambda m: [f'!collectBlocks("coal_ore", {_n(m, 5)})'],
        ),
        (
            rf"(?:collect|mine|get|gather)\s+{_NUM}(?:raw\s+)?iron",
            lambda m: [f'!collectBlocks("iron_ore", {_n(m, 5)})'],
        ),
        (
            rf"craft\s+{_NUM}torch",
            lambda m: [f'!craftRecipe("torch", {max(1, math.ceil(_n(m, 8) / 4))})'],
        ),
        (
            r"(?:kill|hunt|attack)\s+(?:a\s+|some\s+)?(cow|pig|sheep|chicken)",
            lambda m: [f'!attack("{m.group(1)}")'],
        ),
        (r"(?:dig|make|build).*(?:shelter|hole|hide)|hide", lambda m: ["!digDown(3)"]),
        (
            r"(?:go\s+)?(?:back\s+)?(?:to\s+)?(?:the\s+)?surface",
            lambda m: ["!goToSurface()"],
        ),
        (
            r"(?:eat|consume)\s+(?:some\s+|a\s+)?([a-z_]+)",
            lambda m: [f'!consume("{m.group(1)}")'],
        ),
        (
            rf"(?:collect|mine|get|gather)\s+{_NUM}([a-z_ ]+?)s?$",
            lambda m: [
                f'!collectBlocks("{m.group(2).strip().replace(" ", "_")}", {_n(m, 5)})'
            ],
        ),
        (
            rf"craft(?:\s+a|\s+an)?\s+{_NUM}([a-z_ ]+?)s?$",
            lambda m: [
                f'!craftRecipe("{m.group(2).strip().replace(" ", "_")}", {_n(m, 1)})'
            ],
        ),
    ]
    for pattern, build in rules:
        match = re.search(pattern, g)
        if match:
            return build(match)
    return [goal.strip()]
