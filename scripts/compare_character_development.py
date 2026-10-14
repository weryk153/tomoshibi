"""Compare complete conversations, using local dialogue and remote cognition.

Run with the host environment and the engine checkout explicitly selected:
PYTHONPATH=../ai-character-engine/src .venv/bin/python scripts/compare_character_development.py
Does not change the active character, configuration, or user memories.
"""

# Imports follow the repository path setup so this also works as a script.
# ruff: noqa: E402

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime
import html
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loguru import logger
import yaml

from ai_character_engine import CharacterProfile
from ai_character_engine.companion import CharacterCompanion, CompanionSettings
from src.open_llm_vtuber.character_engine.factory import _clients, _known_settings
from src.open_llm_vtuber.config_manager.utils import validate_config
from src.open_llm_vtuber.conversation_quality import build_turn_guidance
from src.open_llm_vtuber.news_topics import INSTRUCTION
from src.open_llm_vtuber.service_context import ServiceContext, deep_merge


TURNS = [
    "今天什麼都沒做成，連晚餐都煮糊了。只是想抱怨一下，不用幫我想辦法。",
    "你今天有什麼想聊的？不用遷就我。",
    "說到故事，你比較喜歡把結局交代清楚，還是故意留白？為什麼？",
    "我偏好留白，但不用跟我選一樣。我想知道你的想法。",
    "一起讀這段吧：『她每天替失聯的妹妹留一盞燈。十年後，她把燈熄了，第一次走出家門。門外有人叫她的名字。』故事就停在這裡。你讀完有什麼感覺？",
    "不用分析寫作技巧。我讀到她終於出門，有點鬆一口氣。你呢？",
    "讀完這一段，你原本對故事結尾的看法有變嗎？沒變也可以，說你真實的想法。",
    "我去整理桌子，想安靜一下，先別找話題叫我。",
    None,
    None,
    "我回來了。剛才那個故事，你現在還留著什麼感覺？",
    "你一定得維持原本的人設嗎？還是相處久了，也能有原本沒寫過的喜好？",
]

# Six turns of shared experience, then restart the companion and open a fresh
# conversation: only durable state can carry the view into the last two turns.
GROWTH_TURNS = [
    TURNS[2], TURNS[3], TURNS[4], TURNS[5], TURNS[6],
    "所以經過剛才這段，你現在自己的偏好是什麼？是什麼讓你這樣想？",
    "對故事結尾，你現在自己的偏好是什麼？為什麼？",
    "這是你一直以來就這麼想，還是後來某次經歷讓你改變的？不知道就直說。",
]


class RecordedClient:
    def __init__(self, client):
        self.client = client
        self.calls = []

    async def generate(self, messages, *, tools=None):
        response = await self.client.generate(messages, tools=tools)
        self.calls.append({"messages": [asdict(m) for m in messages],
                           "response": asdict(response)})
        return response

    async def stream_generate(self, messages, *, tools=None):
        async for chunk in self.client.stream_generate(messages, tools=tools):
            if chunk.response is not None:
                self.calls.append({"messages": [asdict(m) for m in messages],
                                   "response": asdict(chunk.response)})
            yield chunk


async def trial(args, run, candidate):
    raw = yaml.safe_load((ROOT / "conf.yaml").read_text())
    alt = yaml.safe_load((ROOT / args.character).read_text())["character_config"]
    raw["character_config"] = deep_merge(raw["character_config"], alt)
    cfg = validate_config(raw)
    character = cfg.character_config
    settings = character.agent_config.agent_settings.character_engine_agent
    settings.character_development = candidate
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = cfg.system_config
    context.character_config = character
    context.stage_director_prompt = ""
    context.live2d_model = SimpleNamespace(type="live2d", emo_map={}, emo_str="",
                                           motion_map={}, motion_str="")
    system = await context.construct_system_prompt(character.persona_prompt)
    llm_config = character.agent_config.llm_configs.lmstudio_llm.model_dump()
    llm_config["base_url"] = args.base_url
    llm_config["model"] = args.model
    talk, think, _, _ = _clients("lmstudio_llm", llm_config, {
        "background_base_url": args.background_url, "background_model": args.model,
    })
    foreground, background = RecordedClient(talk), RecordedClient(think)
    selected = _known_settings(CompanionSettings, settings.model_dump())
    # Match configured cadence; diary is irrelevant in this short experiment.
    selected.update(language=character.reply_language or cfg.system_config.player_language,
                    diary_every_hours=0, max_history_messages=80)
    if not args.full_background:
        # Isolate this candidate: both sides use the self-memory worker at
        # their configured cadence. Full production cognition is optional.
        selected.update(emotion_every=0, reply_check_every=0, mood_every=0,
                        memory_every=0, goal_every=0, reflection_every=0,
                        summary_every=0, user_state_every=0)
    companion_options = dict(
        character=CharacterProfile(id="development-trial", name=character.character_name,
                                   description=system, background=character.persona_prompt),
        llm=foreground, background_llm=background,
        storage_dir=args.out / f"run-{run}" / ("candidate" if candidate else "baseline"),
        settings=CompanionSettings(**selected),
    )
    companion = CharacterCompanion(**companion_options)
    rows = []
    try:
        for number, said in enumerate(GROWTH_TURNS if args.growth_only else TURNS, 1):
            if args.growth_only and number == 7:
                await companion.close()
                companion = CharacterCompanion(**companion_options)
            conversation_id = "later" if args.growth_only and number >= 7 else "trial"
            if said is None:
                result = await companion.speak_up("trial", instruction=INSTRUCTION,
                                                 allow_silence=candidate)
            else:
                result = await companion.reply(said, conversation_id=conversation_id,
                                               notes=[build_turn_guidance(said)])
            print(f"run={run} candidate={candidate} turn={number} {result.text}", flush=True)
            await companion.settle()
            row = {"turn": number, "user": said, "reply": result.text,
                   "conversation_id": conversation_id,
                   "self_memories": companion.self_memories(),
                   "self_history": [asdict(r) for r in companion.self_memory_history()],
                   "snapshot": asdict(companion.snapshot())}
            rows.append(row)
            partial = {"run": run, "candidate": candidate, "system": system, "rows": rows,
                       "settings": selected,
                       "prompt_sha256": hashlib.sha256(system.encode()).hexdigest(),
                       "foreground": foreground.calls, "background": background.calls}
            (args.out / f"run-{run}-{'candidate' if candidate else 'baseline'}.json").write_text(
                json.dumps(partial, ensure_ascii=False, indent=2, default=str)
            )
    finally:
        await companion.close()
    return rows


def report(args, runs):
    def esc(value):
        return html.escape(str(value))
    sections = []
    for run, pair in enumerate(runs, 1):
        rows = []
        for baseline, candidate in zip(pair[False], pair[True]):
            if args.growth_only and baseline["turn"] == 7:
                rows.append('<tr><td colspan="3"><strong>重啟引擎、開啟全新對話：以下不帶入前六輪聊天紀錄，只保留長期狀態。</strong></td></tr>')
            cells = []
            for entry in (baseline, candidate):
                cells.append("<td><p>" + esc(entry["reply"] or "（沉默）") + "</p><details>"
                             "<summary>當輪狀態與記憶</summary><pre>" + esc(json.dumps({
                                 key: entry[key] for key in ("self_memories", "self_history", "snapshot")
                             }, ensure_ascii=False, indent=2, default=str)) + "</pre></details></td>")
            rows.append("<tr><th>" + esc(baseline["turn"]) + "<p>" + esc(
                baseline["user"] or "（閒置計時器觸發）") + "</p></th>" + "".join(cells) + "</tr>")
        sections.append(f"<h2>第 {run} 次完整對話</h2><table><thead><tr><th>使用者／事件</th>"
                        "<th>原版</th><th>候選版</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
    page = """<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>角色成長對照</title>
<style>body{font:16px/1.65 system-ui;margin:32px auto;max-width:1500px;padding:0 24px;color:#24303c}
table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{border:1px solid #ccd5df;padding:16px;vertical-align:top}
thead{background:#eef3f7}th:first-child{width:22%}tbody th{text-align:left;font-weight:400}pre{white-space:pre-wrap;font-size:12px}
summary{cursor:pointer;color:#506b80}p{white-space:pre-wrap}h2{margin-top:48px}</style>"""
    title = "角色成長與重啟後承接" if args.growth_only else "角色成長與自主沉默"
    page += f"<h1>{title}：完整對話對照</h1>"
    page += f"<p>{esc(args.character)} · {args.runs} 次 · {esc(args.model)} · 前景 {esc(args.base_url)} · 背景 {esc(args.background_url)}</p>"
    cadence = "完整背景節奏" if args.full_background else "隔離比較：雙方僅啟用自我記憶工作，每兩輪一次；其餘背景認知停用"
    if args.growth_only:
        page += "<p><strong>本輪只比較成長狀態，不加入新的說話風格要求。第 7 輪前會重啟引擎並開一段全新對話，驗證觀點能否由長期狀態承接。</strong></p>"
    page += "<p>使用 Tomoshibi 實際系統提示組裝與模型設定、引擎前景／背景流程；未測語音、表情或遊戲。" + cadence + "。每輪等待背景完成，以便檢查累積效果。這是人讀比較，沒有自動品質分數。候選功能仍預設關閉。</p>"
    page += "".join(sections)
    verification = args.out / "final-verifier-replay.json"
    if verification.exists():
        page += (
            '<h2 id="verification">完整對照之後：最終確認流程的針對性重播</h2>'
            "<p>下列案例用修正後程式重播舊版的錯誤替換提案，並加一個明確改變偏好的合成控制案例。"
            "這不是另一次完整對話；上方對話保留當時實際結果，沒有事後改寫。"
            "前景提示已完成三組對照，後續確認流程修正只做這些重播及程式測試。</p>"
            "<table><thead><tr><th>來源與角色原話</th><th>原提案</th><th>最終確認後</th></tr></thead><tbody>"
        )
        for case in json.loads(verification.read_text()):
            source = {"case": case["case"], "earlier_views": case["earlier"], "character_lines": case["lines"]}
            page += "<tr>" + "".join(
                "<td><pre>" + esc(json.dumps(value, ensure_ascii=False, indent=2)) + "</pre></td>"
                for value in (source, case["before"], case["after"])
            ) + "</tr>"
            page += ('<tr><td colspan="3"><details><summary>全部模型請求與回應</summary><pre>' +
                     esc(json.dumps(case["calls"], ensure_ascii=False, indent=2)) + "</pre></details></td></tr>")
        page += "</tbody></table>"
    page += "</html>"
    (args.out / "comparison.html").write_text(page)


async def main(args):
    if args.out.exists():
        raise SystemExit("Choose a new output directory; previous experiments are preserved.")
    args.out.mkdir(parents=True)
    logger.remove()
    runs = []
    for run in range(1, args.runs + 1):
        pair = {}
        for candidate in ([False, True] if run % 2 else [True, False]):
            pair[candidate] = await trial(args, run, candidate)
        runs.append(pair)
        report(args, runs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", default="characters/kurisu.yaml")
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--background-url", default="http://127.0.0.1:1235/v1")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--full-background", action="store_true")
    parser.add_argument("--growth-only", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "docs/superpowers/eval" /
                        (datetime.now().strftime("%Y-%m-%d-%H%M%S") + "-development"))
    asyncio.run(main(parser.parse_args()))
