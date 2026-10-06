"""翻譯審核的人讀對照：真的對話裡她的語音翻譯，逐批跑 TranslationAuditor。

從 logs/debug_2026-10-0*.log 抓 `LLM translate: '原' -> '譯'` 後面緊接著
`Audio translated (R=.. != V=..)` 的那幾句（語音翻譯，V 是目標語言），依當時
載入的角色分組；每組取幾句（加上看起來就怪的：整句英文、沒有假名），照正式
流程每 4 句問一次背景模型。角色的名字與口頭禪從 characters/<conf_uid>.yaml 讀。

輸出 docs/superpowers/eval/2026-10-06-translation-audit.html（gitignored）：
原｜譯｜issues｜建議｜人判。BAD 是人判「明顯譯錯」的句子：標了＝抓到，沒標＝
漏報；不在 BAD 裡卻被標＝誤報（頁面上逐句列出，人再看一次）。

    uv run python scripts/eval_translation_audit.py [--logs ../tomoshibi/logs]
        [--characters ../tomoshibi/characters] [--base-url http://127.0.0.1:1235/v1]
        [--model qwen/qwen3.5-9b] [--list]
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.open_llm_vtuber.background_llm import ChatClient  # noqa: E402
from src.open_llm_vtuber.translate import audit  # noqa: E402

OUT = ROOT / "docs/superpowers/eval/2026-10-06-translation-audit.html"
# (conf_uid, 日期, 取幾句)
GROUPS = [
    ("kurisu", "2026-10-01", 12),
    ("kurisu", "2026-10-02", 5),
    ("char_16560406", "2026-10-02", 12),
    ("task3", "2026-10-06", 8),
    ("pekora", "2026-10-06", 12),
]

# 人判：明顯譯錯的句子（原句 → 錯在哪）。沒列的當作譯得可以。
_STILL_ZH = "沒翻，還是中文"
_NABEN = "混進中文「那边」"
BAD: dict[str, str] = {
    "安安。": _STILL_ZH,
    "樹皮大概是某個故事傳開來的吧。": _STILL_ZH,
    "凌晨兩點了......這時間,費倫跟修塔爾克應該又往北邊去遠方了吧。": "費倫→フェレン（應為フェルン）",
    "Asia/Taipei 00:14 Asia/Tokyo": "多出東京 00:14",
    "這時間點在臺北已經是凌晨了,我剛剛看了一下,最近好像有幾部新番動畫跟新電玩都在這個月要發售......": _STILL_ZH,
    "對喔,你那邊都凌晨了,我剛想起來,最近好像有幾部新番動畫和電玩都在這個十月開始播放或發售。": _NABEN,
    "其實我剛剛在查一下這個月的動漫和電玩......你那邊現在是凌晨幾點啊?": _NABEN,
    "時鐘剛轉到 00:15,這裡都快凌晨了,你那邊現在是什麼時段?": _NABEN,
    "喂,野兔......你那邊現在是凌晨喔?": _NABEN,
    "懂了嗎?": _STILL_ZH,
    "句子其實就是由「主詞動詞副詞」組成的,就像我們說話一樣自然喔!": _STILL_ZH,
    "那到底是什麼奇怪的中文諧音啊?": _STILL_ZH,
    "本小姐最討厭被跟紅蘿蔔扯上關係了耶!": _STILL_ZH,
    "「人參」明明是「紅蘿蔔」耶!": _STILL_ZH,
    "剛才那個「人參」的蠢樣還沒修正,你就想直接棄權逃跑啦?": _STILL_ZH,
    "本小姐可沒那麼好說話喔!": _STILL_ZH,
    "別像剛才那樣打錯字喔,要從嘴巴裡發出來讓我「聽」清楚喔!": "整句英文",
    "既然你這麼「隨便」,那本小姐就順便教你一句超重要的「拜託」吧!": "整句英文",
    "既然你不想學那些讓人頭痛的日語,那我們聊點輕鬆的?": "整句英文",
    "不過「好」這種敷衍的回應也太沒禮貌了吧?": "「へったくもな」不是日文",
}
# 說得過去也說得過去不好（生硬、輕微走意、「本小姐」「哈哈哈」原樣留著）：不計。
EITHER = {
    "不過,與其擔心時間上的連帶關係,不如先把眼前的這個大工程做好比較實際吧。",
    "畢竟你剛才那番話,聽起來像是......某種「自我安慰」吧?",
    "你要是覺得煩,就先離開好了,別再讓我有機會說這種「囉嗦」的話。",
    "欸,都半夜了,你那邊應該也剛睡醒或是還沒睡吧?",
    "哎呀,一直等我也覺得有點尷尬呢......",
    "哈哈哈,「What does yourlin」?",
    "哈哈哈,「Yeah」?",
    "哈哈哈!",
    "不過可別得意忘形喔,要是再讓我覺得被無視或是你一直一副「我很受傷」的樣子,本小姐可真的會生氣喔!",
    "你這是在跟本小姐玩「投降遊戲」喔?",
    "不過既然你安靜了,本小姐就勉為其難陪你說說話......你最近有在追什麼新動畫嗎?",
}

_UID = (
    re.compile(r"conf_uid='([^']+)'"),
    re.compile(r"'conf_uid': '([^']+)'"),
)
_TRANSLATE = re.compile(r"LLM translate: '(.*)' -> '(.*)' \| \{\}\s*$")
_AUDIO = re.compile(r"Audio translated \(R=(\w+) != V=(\w+)\)")
_KANA = re.compile(r"[぀-ヿ]")
_LATIN = re.compile(r"[A-Za-z]")
_LETTER = re.compile(r"[^\W\d_]")


def _odd(translated: str, target: str) -> bool:
    """看起來就怪：大半是拉丁字母，或目標是日文卻沒有假名。"""
    letters = len(_LETTER.findall(translated)) or 1
    if len(_LATIN.findall(translated)) * 2 >= letters:
        return True
    return target == "ja" and not _KANA.search(translated)


def read_logs(logs: Path) -> dict[tuple[str, str], list[tuple[str, str, str]]]:
    """(conf_uid, 日期) → [(原句, 譯句, 目標語言)]，去重、照時間順序。"""
    found: dict[tuple[str, str], list] = OrderedDict()
    for path in sorted(logs.glob("debug_2026-10-0*.log")):
        date = path.stem.removeprefix("debug_")
        uid, pending = "?", None
        for line in path.read_text("utf-8", errors="replace").splitlines():
            if "conf_uid" in line and (
                "load_cache" in line or "New character config" in line
            ):
                for pattern in _UID:
                    match = pattern.search(line)
                    if match:
                        uid = match.group(1)
                        break
            match = _TRANSLATE.search(line)
            if match:
                pending = match.groups()
                continue
            match = _AUDIO.search(line)
            if match and pending:
                original, translated = pending
                pair = (original, translated, match.group(2))
                rows = found.setdefault((uid, date), [])
                if pair not in rows:
                    rows.append(pair)
            pending = None
    return found


def pick(rows: list, count: int) -> list:
    """怪的全拿，再平均取到 count 句。"""
    odd = [row for row in rows if _odd(row[1], row[2])]
    rest = [row for row in rows if row not in odd]
    step = max(1, len(rest) // max(1, count))
    return odd + rest[::step][:count]


def character_terms(characters: Path, uid: str) -> dict:
    path = characters / f"{uid}.yaml"
    try:
        cc = yaml.safe_load(path.read_text("utf-8"))["character_config"]
    except Exception:
        return {"character_name": uid, "protected_names": {}, "catchphrases": {}}
    return {
        "character_name": cc.get("character_name") or uid,
        "protected_names": cc.get("protected_names") or {},
        "catchphrases": cc.get("catchphrases") or {},
    }


class MemoryStore:
    def __init__(self):
        self.entries: list[dict] = []

    def record(self, entries):
        self.entries.extend(entries)


class TimedClient:
    def __init__(self, inner):
        self.inner = inner
        self.seconds: list[float] = []
        self.replies: list[str] = []

    async def complete(self, messages):
        start = time.perf_counter()
        try:
            reply = await self.inner.complete(messages)
        finally:
            self.seconds.append(time.perf_counter() - start)
        self.replies.append(reply)
        return reply


async def run(args) -> list[dict]:
    found = read_logs(Path(args.logs))
    client = TimedClient(
        ChatClient(
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=audit.TIMEOUT_SECONDS + 5,
            request_options={
                "temperature": 0,
                "max_tokens": audit.MAX_TOKENS,
                "reasoning_effort": "none",
            },
        )
    )
    rows = []
    for uid, date, count in GROUPS:
        chosen = pick(found.get((uid, date), []), count)
        if args.list:
            for original, translated, target in chosen:
                print(f"{uid}\t{date}\t{target}\t{original}\t{translated}")
            continue
        terms = character_terms(Path(args.characters), uid)
        store = MemoryStore()
        auditor = audit.TranslationAuditor(
            client,
            store,
            character=terms["character_name"],
            names=list(terms["protected_names"]),
            catchphrases=terms["catchphrases"],
        )
        for original, translated, target in chosen:
            await auditor.submit(original, translated, target)
        await auditor.flush()
        by_line = {(e["original"], e["translated"]): e for e in store.entries}
        for original, translated, target in chosen:
            entry = by_line.get((original, translated))
            rows.append(
                {
                    "uid": uid,
                    "date": date,
                    "target": target,
                    "original": original,
                    "translated": translated,
                    "audited": entry is not None,
                    "issues": (entry or {}).get("issues", []),
                    "suggest": (entry or {}).get("suggest", {}),
                }
            )
    rows_seconds = client.seconds
    for row in rows:
        row["bad"] = BAD.get(row["original"])
        flagged = bool(row["issues"])
        if not row["audited"]:
            row["verdict"] = "dropped"
        elif row["original"] in EITHER:
            row["verdict"] = "either"
        elif row["bad"] and flagged:
            row["verdict"] = "caught"
        elif row["bad"]:
            row["verdict"] = "missed"
        elif flagged:
            row["verdict"] = "false"
        else:
            row["verdict"] = "ok"
    return rows, rows_seconds


VERDICT = {
    "caught": ("抓到", "#1b7f3b"),
    "missed": ("漏報", "#b3261e"),
    "false": ("誤報？", "#b26a00"),
    "ok": ("沒標", "#666"),
    "either": ("兩可", "#666"),
    "dropped": ("沒審到", "#666"),
}


def render(rows, seconds, args) -> str:
    counts = {k: sum(r["verdict"] == k for r in rows) for k in VERDICT}
    bad = sum(1 for r in rows if r["bad"])
    flagged = sum(1 for r in rows if r["issues"])
    batches = len(seconds)
    avg = sum(seconds) / batches if batches else 0

    def cell(text):
        return html.escape(text or "")

    body = []
    for r in rows:
        label, color = VERDICT[r["verdict"]]
        issues = "<br>".join(
            f"<b>{cell(i['kind'])}</b> {cell(i['detail'])}" for i in r["issues"]
        )
        suggest = "<br>".join(
            f"{kind}: {cell(s)} → {cell(t)}"
            for kind, pairs in (r["suggest"] or {}).items()
            for s, t in pairs.items()
        )
        body.append(
            f"<tr><td>{cell(r['uid'])}<br><small>{r['date']}→{r['target']}</small></td>"
            f"<td>{cell(r['original'])}</td><td>{cell(r['translated'])}</td>"
            f"<td>{issues}</td><td>{suggest}</td>"
            f"<td style='color:{color}'><b>{label}</b><br><small>{cell(r['bad'])}</small></td></tr>"
        )
    return f"""<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>翻譯審核對照</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--line:#ddd;--head:#f4f4f6}}
@media (prefers-color-scheme: dark){{:root{{--bg:#161618;--fg:#e8e8ea;--line:#333;--head:#222226}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:16px}}
table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}}
th{{background:var(--head);position:sticky;top:0}}
.wrap{{overflow-x:auto}}
</style>
<h1>翻譯審核對照（2026-10-06）</h1>
<p>模型 <code>{cell(args.model)}</code> @ <code>{cell(args.base_url)}</code>；
{len(rows)} 句、{batches} 批、每批平均 {avg:.1f} 秒。</p>
<p>人判明顯譯錯 {bad} 句：抓到 {counts["caught"]}、<b>漏報 {counts["missed"]}</b>。
模型標了 {flagged} 句，其中不在人判清單的 <b>{counts["false"]}</b> 句（誤報候選，逐句再看）。
兩可（不計）{counts["either"]} 句；沒審到（整批丟掉）{counts["dropped"]} 句。</p>
<div class="wrap"><table>
<tr><th>角色</th><th>原句</th><th>譯句</th><th>issues</th><th>建議</th><th>判</th></tr>
{"".join(body)}
</table></div>
<details><summary>原始 JSON</summary><pre>{cell(json.dumps(rows, ensure_ascii=False, indent=1))}</pre></details>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", default=str(ROOT / "logs"))
    parser.add_argument("--characters", default=str(ROOT / "characters"))
    parser.add_argument("--base-url", default="http://127.0.0.1:1235/v1")
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    parser.add_argument("--list", action="store_true", help="只列出選到的句子")
    args = parser.parse_args()
    rows, seconds = asyncio.run(run(args))
    if args.list:
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(rows, seconds, args), "utf-8")
    counts = {k: sum(r["verdict"] == k for r in rows) for k in VERDICT}
    print(json.dumps(counts, ensure_ascii=False), f"batches={len(seconds)}")
    print(OUT)


if __name__ == "__main__":
    main()
