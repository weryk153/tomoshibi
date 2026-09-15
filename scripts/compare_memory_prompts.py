#!/usr/bin/env python3
"""舊新整理提示詞的並排對照：5 段真實對話 × 各跑 5 次。

用法：
    uv run scripts/compare_memory_prompts.py <舊版 memory_core.py 的 git ref> \
        <對話json1> <對話json2> ... --runs 5 --out docs/superpowers/eval/x.html

從每段對話取「最後一輪」（最後一則 human + 緊接的 ai）當這輪對話，該對話現有的
core_memory.md 當「現有記憶」，self_memory.md 當「現有的自己的記憶」（舊版沒有這
個參數，只餵 core）。LLM 走 conf.yaml 裡對話用的那一顆（resolve_consolidation_llm），
temperature 照 _request_rewrite 的 0.3。

只讀 chat_history/ 底下的對話與記憶檔，絕不寫入 —— load_core_memory /
load_self_memory 都是讀函式，這支腳本從不呼叫任何寫入或整理落地的函式。

輸出一頁 HTML：每段對話一區，區內 5 列，每列左舊右新，全文不截斷。
"""

import argparse
import ast
import asyncio
import html
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.open_llm_vtuber import memory_core  # noqa: E402
from src.open_llm_vtuber.config_manager.utils import read_yaml, validate_config  # noqa: E402

_OLD_TMP = Path(".superpowers-old-memory-core.py")


def _extract_function_source(src: str, func_name: str) -> str:
    """用 ast 從整份原始碼裡挖出單一函式的原始文字（含 def 與縮排）。"""
    tree = ast.parse(src)
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func_name
        ):
            lines = src.splitlines(keepends=True)
            return "".join(lines[node.lineno - 1 : node.end_lineno])
    raise ValueError(f"找不到函式 {func_name}")


def _load_old_module(ref: str):
    """載入舊版 memory_core.py，只需要裡面的 build_consolidation_prompt。

    先試「用套件名載入」這條路（舊檔用 `.utils.path_safety` 這種相對 import，
    直接當獨立模組載入會炸）。這條路失敗（例如相對 import 解不開）就退回只挖出
    build_consolidation_prompt 這個函式本體——它是純函式，函式體裡沒有任何 import，
    直接 exec 在一個乾淨的 namespace 裡就能跑。
    """
    src = subprocess.check_output(
        ["git", "show", f"{ref}:src/open_llm_vtuber/memory_core.py"], text=True
    )
    _OLD_TMP.write_text(src, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location("old_memory_core", _OLD_TMP)
        mod = importlib.util.module_from_spec(spec)
        # 舊檔用相對 import（.utils.path_safety）；用套件名載入才解得開
        mod.__package__ = "src.open_llm_vtuber"
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(
            f"[warn] 整檔載入舊模組失敗（{e}），改用只挖函式本體的 fallback",
            file=sys.stderr,
        )
        func_src = _extract_function_source(src, "build_consolidation_prompt")
        ns: dict = {}
        exec(func_src, ns)  # noqa: S102 - 純函式、無 import，字串來自 git show 的專案原始碼

        class _Shim:
            pass

        shim = _Shim()
        shim.build_consolidation_prompt = ns["build_consolidation_prompt"]
        return shim
    finally:
        _OLD_TMP.unlink(missing_ok=True)


def _last_turn(messages: list) -> tuple[str, str]:
    human = ai = None
    for m in reversed(messages):
        if m.get("role") == "ai" and ai is None:
            ai = m.get("content", "")
        elif m.get("role") == "human" and ai is not None:
            human = m.get("content", "")
            break
    if human is None or ai is None:
        raise SystemExit("找不到完整的一輪（human + ai）")
    return human, ai


def _character_name(messages: list) -> str:
    for m in messages:
        if m.get("role") == "ai" and m.get("name"):
            return m["name"]
    return ""


_MARKER_CONVERSATION = "【對話記憶】"
_SELF_MARKER_RE = re.compile(r"【.+自己】")


def _has_both_markers(text: str) -> bool:
    return _MARKER_CONVERSATION in text and bool(_SELF_MARKER_RE.search(text))


async def _safe_request(base_url, model, prompt, api_key, extra_body) -> str:
    """單次呼叫失敗不能讓整支腳本停下——把例外文字當成這格的輸出，繼續跑下一格。"""
    try:
        return await memory_core._request_rewrite(
            base_url, model, prompt, api_key, extra_body
        )
    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"


async def _main(args):
    old = _load_old_module(args.old_ref)
    conf = validate_config(read_yaml("conf.yaml"))
    base_url, model, api_key, extra_body = memory_core.resolve_consolidation_llm(
        conf.character_config
    )
    cap = getattr(conf.character_config, "core_memory_max_chars", 1500)

    sections = []
    new_marker_hits = 0
    new_marker_total = 0
    for path in args.conversations:
        p = Path(path)
        conf_uid = p.parent.name
        history_uid = p.stem
        messages = json.loads(p.read_text(encoding="utf-8"))
        user_input, ai_response = _last_turn(messages)
        name = _character_name(messages)
        current = memory_core.load_core_memory(conf_uid, history_uid)
        current_self = memory_core.load_self_memory(conf_uid)

        old_prompt = old.build_consolidation_prompt(
            current, user_input, ai_response, cap, character_name=name
        )
        new_prompt = memory_core.build_consolidation_prompt(
            current,
            user_input,
            ai_response,
            cap,
            character_name=name,
            current_self=current_self,
        )
        rows = []
        for i in range(args.runs):
            o = await _safe_request(base_url, model, old_prompt, api_key, extra_body)
            n = await _safe_request(base_url, model, new_prompt, api_key, extra_body)
            rows.append((o, n))
            new_marker_total += 1
            if _has_both_markers(n):
                new_marker_hits += 1
            print(f"{p.name} run {i + 1}/{args.runs} done", file=sys.stderr)
        sections.append(
            (p.name, name, current, current_self, user_input, ai_response, rows)
        )

    print(
        f"[marker] 新提示詞輸出同時含兩個標記：{new_marker_hits}/{new_marker_total}",
        file=sys.stderr,
    )

    out = [
        "<meta charset=utf-8><style>body{font-family:system-ui;max-width:1400px;margin:auto}"
        "pre{white-space:pre-wrap;border:1px solid #ccc;padding:8px;font-size:13px}"
        "table{width:100%;border-collapse:collapse}td{vertical-align:top;width:50%;padding:4px}"
        ".ctx{background:#f6f6f6}</style>"
    ]
    for fname, name, current, current_self, ui, ai, rows in sections:
        out.append(f"<h2>{html.escape(fname)}（{html.escape(name)}）</h2>")
        out.append("<details><summary>這輪對話與現有記憶</summary>")
        out.append(
            f"<pre class=ctx>對方說：{html.escape(ui)}\n\n{html.escape(name)}回：{html.escape(ai)}</pre>"
        )
        out.append(
            f"<pre class=ctx>現有對話記憶：\n{html.escape(current) or '（空）'}</pre>"
        )
        out.append(
            f"<pre class=ctx>現有她自己的記憶：\n{html.escape(current_self) or '（空）'}</pre></details>"
        )
        out.append("<table><tr><th>舊提示詞</th><th>新提示詞</th></tr>")
        for i, (o, n) in enumerate(rows, 1):
            out.append(
                f"<tr><td><b>run {i}</b><pre>{html.escape(o)}</pre></td>"
                f"<td><b>run {i}</b><pre>{html.escape(n)}</pre></td></tr>"
            )
        out.append("</table>")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out), encoding="utf-8")
    print(f"寫到 {args.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("old_ref")
    ap.add_argument("conversations", nargs="+")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", required=True)
    asyncio.run(_main(ap.parse_args()))
