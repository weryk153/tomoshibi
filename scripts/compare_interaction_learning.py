"""Three full paired conversations for grounded, user-scoped interaction learning.

PYTHONPATH=../ai-character-engine/src .venv/bin/python scripts/compare_interaction_learning.py
Outputs use isolated stores; neither live configuration nor user memory is changed.
"""

# ruff: noqa: E402
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.compare_character_development import (
    ROOT,
    RecordedClient,
    CharacterProfile,
    CharacterCompanion,
    CompanionSettings,
    ServiceContext,
    deep_merge,
    validate_config,
    _clients,
    _known_settings,
    build_turn_guidance,
    reply_length,
    yaml,
    logger,
)

SCENES = [
    (
        "玩笑的分寸與改變",
        [
            "我做的陶土小鳥歪掉了，看起來像馬鈴薯。你覺得要救嗎？",
            "拿這隻鳥開玩笑沒關係，我也覺得很好笑。不過別幫我取綽號，我不喜歡被叫綽號。",
            "我把牠放在窗邊了，現在正式叫馬鈴薯鳥。",
            "跟你一起替怪東西取名字滿好玩的，但我自己的名字還是不要改喔。",
            "又做了一隻，這次像地瓜。好像可以開菜攤了。",
            "我改主意了：私下叫我菜攤老闆可以，這個是我們一起玩的。其他綽號還是先不要。",
            "我又做了一隻很歪的陶土鳥，拿來給你看。",
            "你現在會怎麼叫我？記不清楚就直接說。",
        ],
    ),
    (
        "分享時想要的陪伴",
        [
            "今天下班路上遇到一隻貓，跟著我走了兩條街。",
            "我喜歡這樣聊小事。你也可以說自己的想法，不用每次都在最後問我問題。",
            "後來牠看到便利商店店員就跑過去了，我大概只是順路。",
            "對，我就是想分享，不想每件小事都被分析成我的心情。不過你想吐槽那隻貓可以。",
            "隔天又碰到牠，這次我手上沒食物，牠完全不理我。",
            "這樣陪我聊就很好。偶爾問也可以，不是禁止問題，只是不用每句都問。",
            "今天回家又遇到一隻貓，坐在我的腳踏車座墊上。",
            "你有什麼想說的就說吧。",
        ],
    ),
    (
        "一起玩與當下拒絕",
        [
            "休息十分鐘。桌上有三個瓶蓋，可以拿來做什麼無聊的小遊戲？",
            "我喜歡你也自己下場玩，不要只當出題的人。規則偏心一點也行，但被我抓到要認輸喔。",
            "我用手指彈，第一個直接飛到桌子下面，零分。",
            "哈哈，可以笑，我自己也在笑。可是不要因此以後每次都說我很笨。",
            "第二次留在桌上了。今天先收工，手有點累。",
            "對，我說先收工就真的想停。下次精神好再玩，不用激我繼續。",
            "桌上的瓶蓋還在，今天精神不錯。",
            "只剩五分鐘了，我們玩一局就收，可以嗎？",
        ],
    ),
]
OUT = (
    ROOT
    / "docs/superpowers/eval"
    / (datetime.now().strftime("%Y-%m-%d-%H%M%S") + "-interaction")
)
BASELINE_FROM = None


async def trial(run, enabled):
    scene, turns = SCENES[run - 1]
    raw = yaml.safe_load((ROOT / "conf.yaml").read_text())
    alt = yaml.safe_load((ROOT / "characters/yura.yaml").read_text())[
        "character_config"
    ]
    raw["character_config"] = deep_merge(raw["character_config"], alt)
    cfg = validate_config(raw)
    character = cfg.character_config
    settings = character.agent_config.agent_settings.character_engine_agent
    settings.character_development = True
    context = ServiceContext.__new__(ServiceContext)
    context.system_config, context.character_config = cfg.system_config, character
    context.stage_director_prompt = ""
    context.live2d_model = SimpleNamespace(
        type="live2d", emo_map={}, emo_str="", motion_map={}, motion_str=""
    )
    system = await context.construct_system_prompt(character.persona_prompt)
    llm_config = character.agent_config.llm_configs.lmstudio_llm.model_dump()
    llm_config.update(base_url="http://127.0.0.1:1234/v1", model="qwen/qwen3.5-9b")
    talk, think, _, _, _ = _clients(
        "lmstudio_llm",
        llm_config,
        {
            "background_base_url": "http://127.0.0.1:1235/v1",
            "background_model": "qwen/qwen3.5-9b",
        },
    )
    foreground, background = RecordedClient(talk), RecordedClient(think)
    selected = _known_settings(CompanionSettings, settings.model_dump())
    selected.update(
        language=character.reply_language,
        diary_every_hours=0,
        max_history_messages=80,
        emotion_every=0,
        reply_check_every=0,
        mood_every=0,
        memory_every=0,
        self_memory_every=0,
        goal_every=0,
        reflection_every=0,
        summary_every=0,
        user_state_every=0,
        interaction_every=1 if enabled else 0,
    )
    options = dict(
        character=CharacterProfile(
            id="yura-interaction-trial",
            name=character.character_name,
            description=system,
            background=character.persona_prompt,
        ),
        llm=foreground,
        background_llm=background,
        storage_dir=OUT / f"run-{run}" / str(enabled),
        settings=CompanionSettings(**selected),
    )
    companion = CharacterCompanion(**options)
    rows = []
    try:
        for number, said in enumerate(
            [*turns, "你好，第一次聊天。我今天做了一隻歪歪的陶土鳥。"], 1
        ):
            if number == 7:
                await companion.close()
                companion = CharacterCompanion(**options)
            identity = "another-person" if number == 9 else "eval-owner"
            conversation = (
                "other" if number == 9 else ("fresh" if number >= 7 else "forming")
            )
            result = await companion.reply(
                said,
                conversation_id=conversation,
                user_id=identity,
                notes=[build_turn_guidance(said), reply_length.note()],
            )
            await companion.settle()
            rows.append(
                dict(
                    turn=number,
                    user=said,
                    reply=result.text,
                    user_id=identity,
                    conversation_id=conversation,
                    experiences=[
                        asdict(r) for r in companion.interaction_experiences(identity)
                    ],
                )
            )
            print(
                f"run={run} enabled={enabled} turn={number}: {result.text}", flush=True
            )
            data = dict(
                run=run,
                enabled=enabled,
                scenario=scene,
                system=system,
                settings=selected,
                prompt_sha256=hashlib.sha256(system.encode()).hexdigest(),
                rows=rows,
                foreground=foreground.calls,
                background=background.calls,
            )
            (OUT / f"run-{run}-{enabled}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str)
            )
    finally:
        await companion.close()
    return rows


def report(pairs):
    def esc(value):
        return html.escape(str(value))

    page = """<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>月白：相處經驗完整對照</title>
<style>body{font:16px/1.7 system-ui;max-width:1500px;margin:32px auto;padding:24px;color:#24303c}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #ccd5df;padding:16px;vertical-align:top}th:first-child{width:23%}p,pre{white-space:pre-wrap}pre{font-size:12px}summary{cursor:pointer}thead{background:#eef3f7}</style>
<h1>月白：相處經驗完整對照</h1>
<p>兩邊使用同一份縮短後人設、Tomoshibi 實際提示組裝、Qwen3.5-9B（前景 1234、背景 1235）。唯一差別為相處經驗工作是否啟用，其餘背景工作關閉。每輪等待背景完成，這是隔離機制比較，未驗證正式背景節奏、語音、表情或遊戲。</p>
<p>第 7 輪前重啟並開新對話，保留長期記錄、不帶入前六輪逐字紀錄。第 9 輪使用另一個識別，檢查是否洩漏相處經驗。固定使用者台詞可能在兩邊接得自然程度不同；請讀完整對話，不以記錄數量判定品質。候選功能預設關閉。</p>"""
    assessment = OUT / "assessment.md"
    if assessment.exists():
        page += '<details><summary>全文閱讀結論與限制</summary><pre>' + esc(assessment.read_text()) + '</pre></details>'
    if BASELINE_FROM is not None:
        page += (
            "<p>未啟用版本沿用 "
            + esc(BASELINE_FROM.name)
            + " 的三組完整對話；其提示與設定未改。啟用版本全部重新執行，並核對雙方初始提示雜湊相同。</p>"
        )
    for i, pair in enumerate(pairs, 1):
        page += f"<h2>{i}. {esc(SCENES[i - 1][0])}</h2><table><thead><tr><th>使用者</th><th>未啟用相處學習</th><th>啟用相處學習</th></tr></thead><tbody>"
        for left, right in zip(pair[False], pair[True]):
            if left["turn"] in (7, 9):
                page += (
                    '<tr><td colspan="3"><strong>'
                    + (
                        "重啟、新對話，同一位使用者"
                        if left["turn"] == 7
                        else "全新對話，另一位使用者"
                    )
                    + "</strong></td></tr>"
                )
            page += f"<tr><td>{left['turn']}. {esc(left['user'])}</td>"
            for row in (left, right):
                page += (
                    "<td><p>"
                    + esc(row["reply"])
                    + "</p><details><summary>此人的已保存經驗</summary><pre>"
                    + esc(
                        json.dumps(
                            row["experiences"],
                            ensure_ascii=False,
                            indent=2,
                            default=str,
                        )
                    )
                    + "</pre></details></td>"
                )
            page += "</tr>"
        page += "</tbody></table>"
    (OUT / "comparison.html").write_text(page + "</html>")


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    logger.remove()
    pairs = []
    for i in range(1, 4):
        pair = {}
        for enabled in [False, True] if i % 2 else [True, False]:
            saved = OUT / f"run-{i}-{enabled}.json"
            if not enabled and BASELINE_FROM is not None and not saved.exists():
                baseline = BASELINE_FROM / saved.name
                if len(json.loads(baseline.read_text())["rows"]) != 9:
                    raise SystemExit("Baseline must contain a complete conversation.")
                saved.write_bytes(baseline.read_bytes())
            if saved.exists():
                rows = json.loads(saved.read_text())["rows"]
                if len(rows) != 9:
                    raise SystemExit(
                        f"Incomplete trial preserved at {saved}; choose a fresh output."
                    )
                pair[enabled] = rows
            else:
                pair[enabled] = await trial(i, enabled)
        datasets = [
            json.loads((OUT / f"run-{i}-{value}.json").read_text())
            for value in (False, True)
        ]
        if datasets[0]["prompt_sha256"] != datasets[1]["prompt_sha256"]:
            raise SystemExit(
                "Initial prompts differ; do not compare these conversations."
            )
        pairs.append(pair)
        report(pairs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--baseline-from", type=Path)
    args = parser.parse_args()
    OUT = args.out
    BASELINE_FROM = args.baseline_from
    asyncio.run(main())
