"""以 WebSocket 驗證後端核心流程，不需 GUI。

用途是前端替換後的回歸：確認連線、初始化、對話記錄與一輪對話都正常。
退出碼 0 表示通過。

需要 LLM 端點可用（見 conf.yaml 的 llm_provider）。
"""

import asyncio
import json
import sys

import websockets

URL = "ws://127.0.0.1:12393/client-ws"


async def recv_until(ws, wanted: set[str], timeout: float) -> list[dict]:
    got = []
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            raw = await asyncio.wait_for(
                ws.recv(), timeout=max(0.5, deadline - loop.time())
            )
        except asyncio.TimeoutError:
            break
        msg = json.loads(raw)
        got.append(msg)
        if msg.get("type") in wanted:
            break
    return got


def evaluate_conversation(got: list[dict]) -> list[str]:
    """檢查一輪對話收到的訊息，回傳偵測到的失敗描述列表（空 list 表示通過）。

    抽成獨立函式是為了讓 main() 與外部驗證腳本共用同一份判斷邏輯，而不是
    各自維護一份、容易兜不起來。

    一輪對話不是只有一則 audio 訊息：SentenceDivider 會把回覆切成多個句子，
    TTSTaskManager.speak() 對每個句子各自呼叫一次（conversation_utils.py:282、
    sentence_divider.py:549-591），每一段的 audio 欄位都可能各自是 None
    （tts_manager.py:150-173）。因此不能只看某一則訊息：
    - 若一則都沒有非空的 audio，判定 TTS 整輪靜默失敗。
    - 但只要求「至少一段」非空——因為 sentence_divider.py:528-547 會合法地把
      收尾的純標點片段單獨 flush 出來，tts_manager.py:54-68 對這種片段本來就
      是刻意送出 audio=None，那不是錯誤，不能因為最後一段剛好是這種片段就
      判定整輪失敗。
    """
    audio = [m for m in got if m.get("type") == "audio"]
    # 結構化錯誤：後端明確以 {"type": "error", ...} 回報失敗
    # （見 websocket_handler.py / service_context.py / single_conversation.py 等）。
    struct_errors = [m for m in got if m.get("type") == "error"]
    # 文字錯誤：有些失敗不是以 error 訊息回報，而是被塞進一輪助手發言的
    # display_text 裡（例如 openai_compatible_llm.py 的 "Error calling the
    # chat endpoint..."），這種情況 type 仍是 "audio"，要另外抓。
    text_errors = [
        m
        for m in got
        if m.get("type") == "audio"
        and "Error calling the chat endpoint"
        in ((m.get("display_text") or {}).get("text") or "")
    ]
    non_empty_audio = [m for m in audio if m.get("audio")]

    failures = []
    if struct_errors:
        msgs = "; ".join(str(m.get("message")) for m in struct_errors)
        failures.append(f"後端回傳結構化錯誤（type=error）：{msgs}")
    elif not audio:
        failures.append("一輪對話沒有任何語音輸出（沒有收到任何 audio 訊息）")
    elif text_errors:
        failures.append("對話回傳錯誤訊息——檢查 conf.yaml 的 LLM 設定與後端日誌")
    elif not non_empty_audio:
        failures.append("收到 audio 訊息，但每一段語音內容都是空的（TTS 整輪靜默失敗）")
    return failures


async def main() -> int:
    failures = []
    async with websockets.connect(URL, max_size=None) as ws:
        got = await recv_until(ws, {"set-model-and-conf"}, 25)
        conf = next((m for m in got if m.get("type") == "set-model-and-conf"), None)
        if conf is None:
            failures.append("沒有收到 set-model-and-conf（初始化失敗）")
        else:
            print("✓ 初始化：收到 set-model-and-conf")

        await ws.send(json.dumps({"type": "fetch-history-list"}))
        got = await recv_until(ws, {"history-list"}, 15)
        hist = next((m for m in got if m.get("type") == "history-list"), None)
        if hist is None:
            failures.append("沒有收到 history-list")
        else:
            print(f"✓ 對話記錄：{len(hist.get('histories', []))} 筆")

        await ws.send(
            json.dumps({"type": "text-input", "text": "你好，簡短回一句就好。"})
        )
        # 注意：不能等第一則 "audio" 訊息就停手——一輪對話通常會切成多個句子，
        # 每個句子各自一則 audio 訊息（見 evaluate_conversation 的說明），如果
        # recv_until 收到第一則就 break，多半只會抓到其中一段，讓下面的
        # evaluate_conversation 形同虛設。改成等 "backend-synth-complete"——
        # 後端在這輪的所有 TTS 任務都 gather 完之後才會送出這則訊息
        # （single_conversation.py:249-251），送出時前面所有 audio 訊息一定都
        # 已經進到 got 裡。"error" 仍保留，讓結構化錯誤可以提早中止等待。
        got = await recv_until(ws, {"error", "backend-synth-complete"}, 240)
        conv_failures = evaluate_conversation(got)
        if conv_failures:
            failures.extend(conv_failures)
        else:
            audio = [m for m in got if m.get("type") == "audio"]
            empty_count = sum(1 for m in audio if not m.get("audio"))
            first = (audio[0].get("display_text") or {}).get("text")
            note = (
                f"（其中 {empty_count} 段內容為空，可能是收尾標點片段）"
                if empty_count
                else ""
            )
            print(f"✓ 對話：收到 {len(audio)} 段語音，首句 {first!r}{note}")

    if failures:
        print("\n未通過：")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print("\n全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
