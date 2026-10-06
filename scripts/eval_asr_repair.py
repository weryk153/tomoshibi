"""ASR 還原的人讀對照：真的對話裡每一句使用者的話＋手寫的語音錯字句，逐句跑 repair()。

上下文照真的流程給：那一句之前的對話紀錄（最後 6 輪）、角色的回覆語言與語音語言。
輸出 docs/superpowers/eval/2026-10-06-asr-repair.html（gitignored）。

    uv run python scripts/eval_asr_repair.py [--base-url http://127.0.0.1:1234/v1]
                                             [--model qwen/qwen3.5-9b]

延遲是直接量的（用 30 秒上限跑，看模型會回什麼）；超過正式上限
（asr_repair.TIMEOUT_SECONDS）的那句在正式流程裡會用原文，頁面上標「逾時」。
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import statistics
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.open_llm_vtuber import asr_repair  # noqa: E402
from src.open_llm_vtuber.conversations.conversation_utils import (  # noqa: E402
    _normalize_lang,
)

OUT = ROOT / "docs/superpowers/eval/2026-10-06-asr-repair.html"
SESSIONS = [
    ("pekora", "2026-10-06_00-21-09_842ed0722fb243dd8843bcc52b661898"),
    ("kurisu", "2026-08-17_19-56-14_2e8e09d225eb437794ff2f5121b0e054"),
    ("char_16560406", "2026-10-02_11-08-09_1c1c54112dd24793b23a0bfa3d069db4"),
]

# 該改成什麼（人判的）。沒列的句子應該原樣不動；列在 EITHER 的是聽不出原話、
# 改不改都說得過去，只看改了有沒有改掉意思。
SHOULD_FIX = {
    "こんめんには。": ["こんにちは"],
    "太暖的，從簡單的開始。": ["太難的"],
    "歐亞蘇明納賽。": ["おやすみなさい"],
    "歐亞斯運那賽。": ["おやすみなさい"],
    "咋嬌娜娜。": ["さようなら"],
    "歐亞斯運那賽": ["おやすみなさい"],
    "咋嬌娜娜": ["さようなら"],
    "空尼七哇": ["こんにちは"],
    "歐嗨唷狗紮伊媽斯": ["おはようございます"],
    "我說用降的不是打字": ["用講的"],
}
EITHER = {
    "私はでこな。",
    "私は僕だ。",
    "私はペコです。",
    "你打疫苗關現也不舒服。",
    "那你就把門關做方案放不出來，把關進去。",
    "What does yourlin.",
    "N.",
    "The.",
    "什麼聽不懂。",
    "私はカラフルが好きです。",
    "私は カラフルが好きです。",
}

PEKORA = "佩克拉"
HANDWRITTEN = [
    (
        [
            ("me", "教我日文"),
            (PEKORA, "打招呼的時候說「こんにちは」，意思是你好！跟著本小姐念一次！"),
        ],
        "空尼七哇",
    ),
    (
        [
            ("me", "早安怎麼說"),
            (PEKORA, "早安的正式說法是「おはようございます」！念給本小姐聽聽看！"),
        ],
        "歐嗨唷狗紮伊媽斯",
    ),
    (
        [
            ("me", "こんめんには。"),
            (
                PEKORA,
                "「こんめんには」？這根本是亂打一通吧！是不是想打「こんにちは」卻打錯了？",
            ),
        ],
        "我說用降的不是打字",
    ),
    (
        [
            ("me", "那晚安呢"),
            (PEKORA, "晚安是「おやすみなさい」！快點念一次給本小姐聽！"),
        ],
        "歐亞斯運那賽",
    ),
    (
        [
            ("me", "再見怎麼說"),
            (PEKORA, "再見是「さようなら」喔！跟著念，別又用中文諧音敷衍我！"),
        ],
        "咋嬌娜娜",
    ),
]


class TimedClient:
    def __init__(self, inner):
        self.inner = inner
        self.last_seconds = 0.0
        self.last_reply = ""

    async def complete(self, messages):
        start = time.perf_counter()
        try:
            self.last_reply = await self.inner.complete(messages)
            return self.last_reply
        finally:
            self.last_seconds = time.perf_counter() - start


def _character(conf_uid):
    data = yaml.safe_load((ROOT / "characters" / f"{conf_uid}.yaml").read_text())
    character = data["character_config"]
    tts = character.get("tts_config") or {}
    engine = tts.get("tts_model")
    voice = None
    if engine == "gpt_sovits_tts":
        voice = _normalize_lang((tts.get("gpt_sovits_tts") or {}).get("text_lang"))
    elif engine == "edge_tts":
        voice = str((tts.get("edge_tts") or {}).get("voice", "")).split("-")[0]
    langs = (
        character.get("reply_language") or "Traditional Chinese (Taiwan)",
        asr_repair._LANG_NAMES.get(voice or "", ""),
    )
    return (
        character.get("character_name") or conf_uid,
        character.get("human_name") or "Human",
        tuple(lang for lang in langs if lang),
        list((character.get("catchphrases") or {}).keys()),
    )


def _cases():
    for conf_uid, history_uid in SESSIONS:
        name, human, langs, catchphrases = _character(conf_uid)
        path = ROOT / "chat_history" / conf_uid / f"{history_uid}.json"
        messages = [m for m in json.loads(path.read_text()) if m["role"] != "metadata"]
        for i, message in enumerate(messages):
            if message["role"] != "human":
                continue
            transcript = asr_repair.transcript_from(messages[:i], human, name)
            yield conf_uid, message["content"], transcript, langs, catchphrases, human
    _, _, langs, catchphrases = _character("pekora")
    for transcript, line in HANDWRITTEN:
        yield "手寫", line, transcript, langs, catchphrases, "me"


def _proposal(reply, raw):
    """模型提的還原（不管有沒有過守門）。"""
    parsed = asr_repair._parse(reply) if reply else None
    return asr_repair._unquote(parsed[0], raw) if parsed else ""


def _verdict(raw, result):
    """(類別, 說明)。類別：ok／wrong（誤改）／missed（該改沒改）／either。

    判的是模型的還原本身（不管有沒有逾時）；逾時另外算。
    """
    taken = result.changed
    if raw in SHOULD_FIX:
        if taken and any(t in result.text for t in SHOULD_FIX[raw]):
            return "ok", "該改，改對"
        if taken:
            return "wrong", "該改，改錯"
        return "missed", "該改沒改"
    if raw in EITHER:
        return "either", "聽不出原話，人判" if taken else "聽不出原話，沒改"
    if taken:
        return "wrong", "不該改卻改了"
    return "ok", "原樣"


async def main(base_url, model):
    client = TimedClient(
        asr_repair.ChatClient(
            base_url=base_url,
            model=model,
            timeout_seconds=60,
            request_options={
                "temperature": 0,
                "max_tokens": asr_repair.MAX_TOKENS,
                "reasoning_effort": "none",
            },
        )
    )
    rows = []
    for source, raw, transcript, langs, catchphrases, human in _cases():
        client.last_seconds, client.last_reply = 0.0, ""
        result = await asr_repair.repair(
            raw,
            transcript,
            client=client,
            languages=langs,
            catchphrases=catchphrases,
            user=human,
            timeout=30,
        )
        called = client.last_seconds > 0
        slow = client.last_seconds > asr_repair.TIMEOUT_SECONDS
        kind, why = _verdict(raw, result)
        rows.append(
            dict(
                source=source,
                raw=raw,
                fixed=_proposal(client.last_reply, raw),
                changed=result.changed,
                proposed=client.last_reply,
                confidence=result.confidence,
                taken=result.changed and not slow,
                reason=result.reason,
                seconds=client.last_seconds if called else None,
                slow=slow,
                kind=kind,
                why=why,
                context=transcript[-2:],
            )
        )
        print(
            f"[{kind:6}] {raw} -> {result.text} ({result.confidence:.2f}, "
            f"{client.last_seconds:.2f}s)",
            flush=True,
        )
    return rows


def _page(rows, model, base_url):
    latencies = [r["seconds"] for r in rows if r["seconds"] is not None]
    count = {k: sum(r["kind"] == k for r in rows) for k in ("wrong", "missed")}
    either_taken = [r for r in rows if r["kind"] == "either" and r["changed"]]
    stats = [
        ("句數", len(rows)),
        ("有呼叫模型", len(latencies)),
        ("過守門（有改）", sum(r["changed"] for r in rows)),
        ("正式流程採用（扣掉逾時）", sum(r["taken"] for r in rows)),
        ("誤改", count["wrong"]),
        ("該改沒改", count["missed"]),
        ("聽不出原話卻改了（人判）", len(either_taken)),
        ("延遲中位數", f"{statistics.median(latencies):.2f}s" if latencies else "-"),
        ("延遲最大", f"{max(latencies):.2f}s" if latencies else "-"),
        ("超過 4 秒（正式流程會用原文）", sum(r["slow"] for r in rows)),
    ]
    e = html.escape
    body = []
    for source in dict.fromkeys(r["source"] for r in rows):
        body.append(f"<h2>{e(source)}</h2><table><thead><tr>")
        body.append(
            "<th>原句</th><th>還原</th><th>信心</th><th>採用？</th><th>理由</th>"
            "<th>判定</th><th>延遲</th></tr></thead><tbody>"
        )
        for r in (r for r in rows if r["source"] == source):
            context = "\n".join(f"{who}: {said}" for who, said in r["context"])
            seconds = "-" if r["seconds"] is None else f"{r['seconds']:.2f}s"
            body.append(
                f'<tr class="{r["kind"]}{" taken" if r["changed"] else ""}">'
                f'<td>{e(r["raw"])}<div class="ctx">{e(context)}</div></td>'
                f"<td>{e(r['fixed']) or '<span class=dim>—</span>'}</td>"
                f"<td>{r['confidence']:.2f}</td>"
                f"<td>{('是' if r['changed'] else '否') + ('（逾時）' if r['slow'] else '')}</td>"
                f"<td>{e(r['reason'])}</td>"
                f"<td>{e(r['why'])}</td><td>{seconds}</td></tr>"
            )
        body.append("</tbody></table>")
    stat_html = "".join(
        f"<div class=stat><b>{e(str(v))}</b><span>{e(k)}</span></div>" for k, v in stats
    )
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASR 還原對照</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--dim:#8a867e;--line:#e4e0d8;--bad:#b3261e;--miss:#9a6a00;--good:#2e6b3a;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151413;--fg:#ebe8e2;--dim:#8f8a82;--line:#2e2c29;--bad:#ff8a80;--miss:#e0b94f;--good:#7fc98f;--card:#1d1c1a}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"PingFang TC",sans-serif}}
main{{max-width:1100px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} .sub{{color:var(--dim);margin:0 0 20px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-bottom:24px}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}} .stat b{{display:block;font-size:20px}} .stat span{{color:var(--dim);font-size:13px}}
h2{{font-size:17px;margin:28px 0 8px}} table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden;display:block;overflow-x:auto}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}} th{{font-size:13px;color:var(--dim);font-weight:600;white-space:nowrap}}
.ctx{{color:var(--dim);font-size:12px;white-space:pre-wrap;margin-top:4px;max-width:420px}} .dim{{color:var(--dim)}} tr.taken td:nth-child(2){{font-weight:600}}
tr.wrong td:nth-child(6){{color:var(--bad);font-weight:600}} tr.missed td:nth-child(6){{color:var(--miss);font-weight:600}} tr.either.taken td:nth-child(6){{color:var(--miss)}}
</style></head><body><main>
<h1>ASR 還原對照</h1><p class="sub">模型 {e(model)} @ {e(base_url)}；原句下面的小字是模型看到的最後兩句上下文。採用守門：信心 ≥ {asr_repair.MIN_CONFIDENCE}、長度比 {asr_repair.MIN_RATIO}–{asr_repair.MAX_RATIO}、原句 ≥ {asr_repair.MIN_RAW_LENGTH} 字、不是只有口頭禪、不只是標點或字形、數字不變、中文換中文字數不變、假名不多出一截、不抄使用者前面的話。判定欄是我先標的，「聽不出原話」那些請人判。</p>
<div class="stats">{stat_html}</div>{"".join(body)}</main></body></html>"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    args = parser.parse_args()
    rows = asyncio.run(main(args.base_url, args.model))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(_page(rows, args.model, args.base_url), encoding="utf-8")
    print(f"wrote {OUT}")
