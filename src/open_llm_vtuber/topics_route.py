"""主動話題：使用者維護一份話題清單，決定她閒下來時聊什麼。

這條路徑的關鍵事實是：她主動說話用的 prompts/utils/proactive_speak_prompt.txt
被後端每次觸發都重讀（prompt_loader.load_util，沒有快取）。所以只要覆寫那個檔，
下一次主動開口就生效，不必重啟。

一份清單，兩種模式：

- 新聞關閉：提示詞只帶這份話題清單，她從自己既有的知識聊起，不碰網路。
- 新聞開啟：每個話題各自當成 Google News 的查詢字抓最新標題，附在話題清單後面。
  同一份清單，差別只在有沒有去抓。

空清單就是空的。沒有任何預設會被偷偷塞回來——那是這個設計最重要的一條，
早期版本用「清單為空就換成預設分類」兜底，結果那幾個預設刪不掉。

狀態存在 prompts/utils/proactive_topics.json，跟它組出來的提示詞放一起。
行為契約由 tests/test_topics_route_behavior.py 釘住。
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from . import news_topics
from .api_guard import forbidden as _forbidden, is_trusted_request as _is_local_request

# --- 界限 --------------------------------------------------------------------

STATE_PATH = os.path.join("prompts", "utils", "proactive_topics.json")

# 上限是護欄：一個亂送的大 POST 不可以把提示詞灌爆，也不可以在新聞開啟時
# 展開成幾百個同步的 RSS 請求。
MAX_TOPICS = 30
MAX_TOPIC_LEN = 200
MIN_INTERVAL_HOURS = 1
MAX_INTERVAL_HOURS = 24
DEFAULT_INTERVAL_HOURS = 6

# 給前端當一鍵新增的建議詞。不會被存下來、也不會硬塞進任何人的清單——只是讓
# 全新的空清單有個起點。使用者想打什麼話題都可以。
SUGGESTIONS = ["科技", "AI", "動漫", "電玩", "國際", "娛樂", "財經", "體育"]

# 閒置時的重新檢查間隔（小時）。新聞關著時不需要照設定的間隔睡那麼久，
# 睡短一點，使用者打開開關後一小時內就會生效。
_IDLE_RECHECK_HOURS = 1
# 開機後延遲多久才跑第一輪，免得啟動被一個網路請求卡住。
_STARTUP_DELAY_SECONDS = 30


# --- 數值整理 ----------------------------------------------------------------

def _clamp_interval(value: Any) -> int:
    """把間隔夾進 [MIN, MAX] 小時；看不懂的值 fail-soft 回預設。"""
    try:
        hours = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS
    return max(MIN_INTERVAL_HOURS, min(MAX_INTERVAL_HOURS, hours))


def _sanitize_topics(raw: Any) -> list[str]:
    """整理話題清單：去空白、丟掉空的、限長、去重、限量，順序保留。

    空的進來就空的出去。**這裡絕對不能有「空就給預設」的兜底**——那正是早期
    版本讓預設分類刪不掉的原因。
    """
    if not isinstance(raw, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        topic = item.strip()[:MAX_TOPIC_LEN]
        if not topic or topic in seen:
            continue
        seen.add(topic)
        cleaned.append(topic)
        if len(cleaned) >= MAX_TOPICS:
            break
    return cleaned


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# --- 狀態檔 ------------------------------------------------------------------

def _default_state() -> dict:
    return {
        "topics": [],
        "news": {"enabled": False, "interval_hours": DEFAULT_INTERVAL_HOURS},
        "last_news_refresh": None,
    }


def _topics_from(data: dict) -> list[str]:
    """讀出話題清單，順便相容更早的雙清單格式。

    早期的檔案把「手動話題」與「新聞分類」分成兩份存。合併成一份時手動的排前面，
    使用者升級後不會掉東西。新的 topics 鍵存在時就以它為準。
    """
    if isinstance(data.get("topics"), list):
        return _sanitize_topics(data["topics"])

    legacy: list[str] = []
    if isinstance(data.get("manual_topics"), list):
        legacy.extend(str(t) for t in data["manual_topics"])
    news = data.get("news")
    if isinstance(news, dict) and isinstance(news.get("categories"), list):
        legacy.extend(str(c) for c in news["categories"])
    return _sanitize_topics(legacy)


def _load_state() -> dict:
    """讀狀態；檔案不存在、壞掉、格式不對，一律回預設。

    fail-soft 是必要的：一個壞掉的狀態檔不可以讓整個設定頁打不開。
    """
    state = _default_state()
    try:
        path = Path(STATE_PATH)
        if not path.is_file():
            return state
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return state
    except Exception as e:
        logger.warning(
            f"[topics] proactive_topics.json unreadable, using defaults: "
            f"{type(e).__name__}"
        )
        return state

    state["topics"] = _topics_from(data)

    news = data.get("news")
    if isinstance(news, dict):
        if isinstance(news.get("enabled"), bool):
            state["news"]["enabled"] = news["enabled"]
        if isinstance(news.get("interval_hours"), (int, float)):
            state["news"]["interval_hours"] = _clamp_interval(news["interval_hours"])

    if data.get("last_news_refresh"):
        state["last_news_refresh"] = str(data["last_news_refresh"])
    return state


def _write_state(state: dict) -> None:
    """原子寫入狀態檔。"""
    path = Path(STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


# --- 話題 → 新聞 -------------------------------------------------------------

def _get_news_module():
    """新聞模組。抽成函式是為了讓測試 monkeypatch 得到同一個物件。"""
    return news_topics


def _queries_for(topics: list) -> list[tuple[str, str]]:
    """把話題清單化成 (顯示標籤, 查詢字)。

    對得到精選關鍵字的就用對照後的查詢字（AI → AI 人工智慧，搜出來的東西好得多），
    對不到的就拿使用者原本打的字去查——他打什麼就搜什麼。順序照他排的。
    """
    hints = dict(_get_news_module().CATEGORIES)
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in topics:
        if not isinstance(item, str):
            continue
        topic = item.strip()
        if not topic or topic in seen:
            continue
        seen.add(topic)
        pairs.append((topic, hints.get(topic, topic)))
    return pairs


def _fetch_blocks_for(topics: list, seen=None, new_titles=None):
    """同步抓每個話題的新聞，回傳 (區塊清單, 有沒有抓到)。

    空清單什麼都不抓。這裡刻意沒有「沒話題就抓全部預設分類」的退路——新聞開著
    但清單是空的，就該安安靜靜什麼都不抓，不要給人驚喜。
    """
    nt = _get_news_module()
    pairs = _queries_for(topics)
    if not pairs:
        return [], False
    return nt.fetch_news_blocks(
        categories=pairs, per_cat=nt.PER_CAT, seen=seen, new_titles=new_titles
    )


def _compose_and_write(state: dict, *, news_blocks=None, got_any: bool = False) -> str:
    """把話題清單（＋可選的新聞）組成提示詞並寫檔，回傳組出來的內容。"""
    nt = _get_news_module()
    content = nt.compose_content(
        manual_topics=state.get("topics", []),
        news_blocks=news_blocks or [],
        got_any=got_any,
    )
    nt.write_prompt(content)
    return content


async def _fetch_news_in_thread(topics: list) -> tuple[list, bool, int]:
    """開新聞時去抓一輪，回傳 (區塊, 有沒有抓到, 標題數)。

    抓取是同步阻塞的（urllib），丟到執行緒避免卡住事件迴圈。任何失敗都當成
    「這輪沒新聞」——絕不讓網路問題炸掉這條路徑。

    跨輪去重：端過的標題從 seen 排除；這輪真的端出去的才寫回去。全部被濾掉或
    抓失敗時不動 seen，否則下一輪會以為這些都端過了。
    """
    nt = _get_news_module()
    try:
        seen = await asyncio.to_thread(nt.load_seen)
    except Exception as e:
        logger.warning(f"[topics] seen load failed, treating as empty: {type(e).__name__}")
        seen = {}

    new_titles: list = []
    try:
        blocks, got_any = await asyncio.to_thread(
            _fetch_blocks_for, topics, seen, new_titles
        )
    except Exception as e:
        logger.warning(f"[topics] news fetch failed: {type(e).__name__}: {e}")
        return [], False, 0

    if new_titles:
        try:
            await asyncio.to_thread(nt.save_seen, nt.mark_seen(seen, new_titles))
        except Exception as e:
            logger.warning(f"[topics] seen save failed: {type(e).__name__}")

    return blocks, got_any, sum(b.count("\n- ") for b in blocks)


async def _refresh(state: dict) -> dict:
    """重新組出提示詞；新聞開著就先抓一輪。

    回傳 {news_ok, news_count}。抓取失敗不會拋——那時只組人設＋話題清單，
    永遠不留下壞檔。全部話題都沒新料時 got_any 是 False，新聞區塊整段省略，
    人設指示會叫她從自己的知識聊起，而不是重複昨天的舊聞。
    """
    blocks, got_any, count = [], False, 0
    if state.get("news", {}).get("enabled"):
        blocks, got_any, count = await _fetch_news_in_thread(state.get("topics", []))

    await asyncio.to_thread(
        _compose_and_write, state, news_blocks=blocks, got_any=got_any
    )
    return {"news_ok": got_any, "news_count": count}


# --- 背景定時更新（不是系統 cron）---------------------------------------------

_refresh_task: Optional[asyncio.Task] = None


async def _refresh_cycle() -> int:
    """跑一輪，回傳下一輪要等幾小時。

    新聞關著時回較短的閒置間隔——不必照設定的間隔睡那麼久，使用者打開開關後
    一小時內就會生效。
    """
    state = await asyncio.to_thread(_load_state)
    if not state.get("news", {}).get("enabled"):
        return _IDLE_RECHECK_HOURS

    interval = _clamp_interval(state["news"].get("interval_hours"))
    result = await _refresh(state)
    state["last_news_refresh"] = _now_iso()
    await asyncio.to_thread(_write_state, state)
    logger.info(
        f"[topics] auto-refresh done (news_ok={result['news_ok']}, "
        f"count={result['news_count']}), next in {interval}h"
    )
    return interval


async def _news_refresh_loop() -> None:
    """定時重抓新聞、重組提示詞。

    取消要乾淨，例外要吞掉——一次抓取失敗只記 log 然後繼續，不可以把整個
    迴圈弄死。
    """
    logger.info("[topics] news auto-refresh loop started")
    try:
        await asyncio.sleep(_STARTUP_DELAY_SECONDS)
        while True:
            try:
                interval = await _refresh_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[topics] auto-refresh cycle error: {type(e).__name__}: {e}")
                interval = _IDLE_RECHECK_HOURS
            await asyncio.sleep(max(1, interval) * 3600)
    except asyncio.CancelledError:
        logger.info("[topics] news auto-refresh loop cancelled")


def start_news_refresh_task() -> None:
    """啟動定時任務（重複呼叫安全）。"""
    global _refresh_task
    if _refresh_task is not None and not _refresh_task.done():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    _refresh_task = loop.create_task(_news_refresh_loop())


async def stop_news_refresh_task() -> None:
    """關機時取消定時任務。"""
    global _refresh_task
    if _refresh_task is None:
        return
    _refresh_task.cancel()
    try:
        await _refresh_task
    except Exception:
        pass
    _refresh_task = None


# --- 端點 --------------------------------------------------------------------

def _state_payload(state: dict) -> dict:
    return {
        "topics": state["topics"],
        "news": state["news"],
        "last_news_refresh": state["last_news_refresh"],
    }


def init_topics_route() -> APIRouter:
    """主動話題的 REST 端點。只接受本機請求。

    - GET  /api/proactive-topics          目前的清單、新聞設定、建議詞
    - POST /api/proactive-topics          存清單與設定，並重組提示詞
    - POST /api/proactive-topics/refresh  立即抓新聞並重組（/refresh-now 同義）
    """
    router = APIRouter()

    @router.get("/api/proactive-topics")
    async def get_topics(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            state = await asyncio.to_thread(_load_state)
        except Exception as e:
            logger.error(f"[topics] read failed: {type(e).__name__}")
            return JSONResponse(
                status_code=500, content={"error": "could not read state"}
            )
        return JSONResponse({**_state_payload(state), "suggestions": SUGGESTIONS})

    @router.post("/api/proactive-topics")
    async def save_topics(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400, content={"ok": False, "error": "Invalid JSON body."}
            )

        # 部分更新：只有 body 裡明確出現的鍵才會被改。
        state = await asyncio.to_thread(_load_state)
        if "topics" in body:
            state["topics"] = _sanitize_topics(body.get("topics"))
        news_in = body.get("news")
        if isinstance(news_in, dict):
            if "enabled" in news_in:
                state["news"]["enabled"] = bool(news_in["enabled"])
            if "interval_hours" in news_in:
                state["news"]["interval_hours"] = _clamp_interval(
                    news_in["interval_hours"]
                )

        try:
            await asyncio.to_thread(_write_state, state)
        except Exception as e:
            logger.error(f"[topics] write failed: {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not write state file."},
            )

        # 存檔後就地重組提示詞，讓話題清單立刻生效。這裡刻意不去抓新聞——那是
        # refresh 的工作，存個設定不該卡住幾秒的網路請求。
        try:
            await asyncio.to_thread(
                _compose_and_write, state, news_blocks=[], got_any=False
            )
            composed = True
        except Exception as e:
            logger.error(f"[topics] prompt recompose failed: {type(e).__name__}")
            composed = False

        return JSONResponse({"ok": True, "composed": composed, **_state_payload(state)})

    # 兩個路徑都收：/refresh 是規格上的名字，/refresh-now 是前端打的。
    @router.post("/api/proactive-topics/refresh")
    @router.post("/api/proactive-topics/refresh-now")
    async def refresh_now(request: Request):
        if not _is_local_request(request):
            return _forbidden()

        state = await asyncio.to_thread(_load_state)
        try:
            result = await _refresh(state)
        except Exception as e:
            logger.error(f"[topics] refresh failed: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500, content={"ok": False, "error": "Refresh failed."}
            )

        if state.get("news", {}).get("enabled"):
            state["last_news_refresh"] = _now_iso()
            try:
                await asyncio.to_thread(_write_state, state)
            except Exception as e:
                logger.warning(
                    f"[topics] could not persist last_news_refresh: {type(e).__name__}"
                )

        return JSONResponse(
            {
                "ok": True,
                "news_enabled": bool(state.get("news", {}).get("enabled")),
                "news_ok": result["news_ok"],
                "news_count": result["news_count"],
                "last_news_refresh": state["last_news_refresh"],
            }
        )

    return router
