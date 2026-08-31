"""角色的長期核心記憶：一份小而精的檔案，每輪對話後由 LLM 背景維護。

兩層式設計（core memory + consolidation，同 MemGPT / Generative Agents 一脈）：

- **注入**：construct_system_prompt 把 chat_history/<conf_uid>/<history_uid>/
  core_memory.md 的內容附在 persona 後面，每輪都帶著。記憶屬於一段對話，不是
  一個角色——新對話從空白開始。
- **整理**：每輪對話結束後背景呼叫 LLM（fire-and-forget，不阻塞對話），
  判斷這輪有沒有值得留下的新事實，有才改寫檔案。

整理用的提示詞（build_consolidation_prompt）是這個模組的靈魂——它決定記憶會
被記成什麼樣子，歷次修正的教訓都寫在它的 docstring 裡。

行為契約由 tests/test_memory_store_behavior.py 釘住。
"""

import asyncio
from collections import OrderedDict
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from .utils.path_safety import safe_join

# --- 大小與頻率的界限 --------------------------------------------------------

CAP_CHARS = 1500  # 記憶檔字數上限的預設值；撞上限時由整理 LLM 自行提煉合併
CAP_MIN = 500  # 低於這個記不住東西
CAP_MAX = 8000  # 高於這個每輪 token 暴增、整理更容易漏

CONSOLIDATE_INTERVAL_DEFAULT = 1  # 每幾輪整理一次；1 = 每輪
CONSOLIDATE_INTERVAL_CHOICES = (1, 3, 5)  # 弱機／本地模型可選 3 或 5 省呼叫


def _coerce_int(value: Any, fallback: int) -> int:
    """設定值是外部來的，什麼垃圾都可能出現；轉不成整數就回 fallback。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _clamp_cap(value: Any) -> int:
    """把字數上限夾進 [CAP_MIN, CAP_MAX]；壞值 fail-soft 回預設。

    fail-soft 是刻意的：垃圾設定值不可以讓整理悄悄停掉。
    """
    n = _coerce_int(value, CAP_CHARS)
    return min(max(n, CAP_MIN), CAP_MAX)


def _clamp_interval(value: Any) -> int:
    """整理頻率只允許 {1, 3, 5}；其他一律回 1（每輪整理，最保守）。"""
    n = _coerce_int(value, CONSOLIDATE_INTERVAL_DEFAULT)
    return n if n in CONSOLIDATE_INTERVAL_CHOICES else CONSOLIDATE_INTERVAL_DEFAULT


# --- 儲存 --------------------------------------------------------------------


def _memory_file(conf_uid: str, history_uid: str) -> Path:
    """記憶檔位置。

    conf_uid 與 history_uid 都是請求可控的。分兩段呼叫 safe_join——先把 conf_uid
    關進 chat_history/，再把 history_uid 關進 chat_history/<conf_uid>/——是刻意的：
    一次呼叫 safe_join("chat_history", conf_uid, history_uid, ...) 只保證結果留在
    chat_history/ 之內，history_uid 帶 "../" 仍能跳出 conf_uid 自己的資料夾、
    寫進另一個角色的目錄，因為那個位置一樣落在 chat_history/ 底下、擋不住。
    分段之後，history_uid 的逃逸目標就是 conf_uid 自己那層，才擋得住。

    呼叫端必須先確定 history_uid 非空——記憶屬於一段對話，沒有對話就沒有記憶。
    """
    char_dir = safe_join("chat_history", conf_uid)
    return Path(safe_join(char_dir, history_uid, "core_memory.md"))


def core_memory_path(conf_uid: str, history_uid: str) -> str:
    """給 route 層用的公開路徑查詢。沒有對話、或路徑不安全時回空字串。

    load/save/clear 三個都吞掉 safe_join 丟出的 ValueError、fail soft 回空字串
    或 False；這個原本沒跟——一個不安全的 conf_uid/history_uid 會讓例外直接炸
    出去。memory_route 的 GET /api/memory 就是這樣裸呼叫這個函式，於是三個姊妹
    函式都能優雅降級的錯誤輸入，這裡會把設定頁的記憶分頁弄成 500。跟手足一致，
    回空字串。
    """
    if not history_uid:
        return ""
    try:
        return str(_memory_file(conf_uid, history_uid))
    except ValueError as e:
        logger.warning(f"[core_memory] unsafe path for {conf_uid}/{history_uid}: {e}")
        return ""


def load_core_memory(conf_uid: str, history_uid: str) -> str:
    """讀出這段對話的記憶；沒有、或讀不到，一律回空字串。

    這條在注入路徑上，絕不能丟例外——檔案系統的問題不可以炸掉對話。

    history_uid 為空（連線還在初始化）時回空字串，不要退回舊的角色層路徑：
    那會變成「有時候讀這裡、有時候讀那裡」。
    """
    if not history_uid:
        return ""
    try:
        f = _memory_file(conf_uid, history_uid)
        return f.read_text(encoding="utf-8").strip() if f.is_file() else ""
    except Exception as e:
        logger.warning(f"[core_memory] load failed for {conf_uid}/{history_uid}: {e}")
        return ""


def _write_memory(conf_uid: str, history_uid: str, text: str) -> None:
    f = _memory_file(conf_uid, history_uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def clear_core_memory(conf_uid: str, history_uid: str) -> bool:
    """忘掉這段對話的全部記憶。

    截斷成空檔而不是刪檔（house rule 不硬刪）；檔案不存在本來就等於已清空。
    """
    if not history_uid:
        return False
    try:
        if _memory_file(conf_uid, history_uid).is_file():
            _write_memory(conf_uid, history_uid, "")
            logger.info(f"[core_memory] cleared for {conf_uid}/{history_uid}")
        return True
    except Exception as e:
        logger.warning(f"[core_memory] clear failed for {conf_uid}/{history_uid}: {e}")
        return False


def save_core_memory(
    conf_uid: str, history_uid: str, content: str, cap: int = CAP_CHARS
) -> bool:
    """整份覆寫記憶（記憶分頁的手動編輯用）。

    超過上限採「照存但警告」：使用者明確打的字尊重原樣，偷偷截斷比超長更意外；
    下一輪整理本來就會把過長內容提煉回上限內。None 視為空字串。
    """
    if not history_uid:
        return False
    try:
        text = (content or "").strip()
        limit = _clamp_cap(cap)
        if len(text) > limit:
            logger.warning(
                f"[core_memory] manual save for {conf_uid}/{history_uid} exceeds cap "
                f"({len(text)} > {limit} chars); stored as-is, will be "
                "compacted on next consolidation"
            )
        _write_memory(conf_uid, history_uid, text)
        logger.info(
            f"[core_memory] manually saved for {conf_uid}/{history_uid} ({len(text)} chars)"
        )
        return True
    except Exception as e:
        logger.warning(f"[core_memory] save failed for {conf_uid}/{history_uid}: {e}")
        return False


# --- 整理（consolidation）----------------------------------------------------


def build_consolidation_prompt(
    current: str,
    user_input: str,
    ai_response: str,
    cap: int,
    character_name: str = "",
) -> str:
    """組出記憶整理用的提示詞。抽成純函式是為了測得到——這段文字決定了記憶會
    被記成什麼樣子，而它出錯時沒有任何徵兆，只會安靜地把錯的事實留在檔案裡。

    舊版把整份記憶框成「關於使用者的長期記憶」，同時要求記「重要事件或對話
    結論」。當結論出自角色自己時，這兩條互相打架：角色的事實沒有欄位可放，
    只能被塞進使用者的主詞。實際結果是芙莉蓮說「我可能就跟著他們往北走」
    之後，記憶寫成「使用者目前正計畫跟隨費倫與修塔爾克前往北方」。

    所以框架改成兩類，並要求每條都寫明主詞——不是再加一條禁令，因為禁令
    （「絕不記 AI 自己說的話」）本來就已經在了，沒有用。

    第二輪修正：第二類原本寫「說過的計畫、表明過的立場」，而「立場」正好是拒絕
    的入口。芙莉蓮說「我沒辦法幫你挑號碼」之後，記憶寫下「她連碰都碰不到」，
    這行從此每一輪都進系統提示——她拒絕一次就被自己的舊台詞釘住，之後逐字重複
    同一句拒絕。使用者連問四次，拿到四次一模一樣的回覆。

    同時擋掉兩類雜訊：聽不清楚的回合（語音辨識失敗，不是任何人的事實），以及
    「測試聲音有沒有通」。實測 53 行的記憶裡這兩類佔了三成，還把 1500 字的上限
    吃掉，逼整理去刪真正該留的東西。

    第三輪修正：主詞從「使用者」改成「對方」。人設裡沒有「使用者」這個概念，它
    一貫用「對方」，而且明文禁止角色主動提起 AI、程式、資料、系統這類詞——「使用
    者」是同一個語域的詞，卻被放在記憶幾乎每一行的開頭，每一輪都注入。已經漏出去
    過：紅莉栖說過「我當然知道你是使用者……你是出現在『現在』這個世界線裡、能自由
    與我交談的物件」。

    不能改用「你」：系統提示是寫給角色看的，那裡的「你」指角色自己，主詞會整個
    混掉。
    """
    who = character_name.strip() or "角色"
    return (
        f"你是這個 AI 角色的記憶管理員。角色的名字是「{who}」。\n"
        "根據下面這輪對話，維護一份「這段關係的長期記憶」。\n\n"
        "規則（嚴格遵守）：\n"
        "- 記兩類事情，兩類都要記：\n"
        "  1. 關於對方的：身分／職業／正在做的事、偏好與習慣、希望被怎麼稱呼、\n"
        "     他明確講過的重要事件。\n"
        f"  2. 關於{who}自己的：說過的計畫、答應過的事、講過的關於自己的來歷或喜好。\n"
        f"- 每一條都必須以「對方」或「{who}」開頭，寫明這件事是誰的。省略主詞不行。\n"
        f"- {who}講的話絕對不可以寫成對方的事實。分不清楚是誰的就整條不要記。\n"
        "- 絕不記：一次性閒聊、寒暄、問候、沒有新資訊的對話。\n"
        f"- 絕不記{who}做不到、不擅長、不會、沒辦法、拒絕、不想談、沒興趣的事。\n"
        "  這種句子寫進記憶之後，\n"
        f"  每一輪都會告訴{who}她做不到，她就照著再拒絕一次，而且逐字重複。\n"
        "  同理也不記她表達過的情緒反應（覺得無奈、感到困惑、有點不耐煩）。\n"
        "- 絕不記聽不清楚、聽錯、猜對方在講什麼的那一輪。那是語音辨識的雜訊，\n"
        "  不是關於任何人的事實。\n"
        "- 絕不記測試、確認聲音有沒有傳到、連線通不通這種操作性的對話。\n"
        "- 用簡短條列，每條一行，繁體中文，台灣用語。\n"
        "- 如果這輪對話沒有任何值得記的新資訊，就原封不動輸出現有記憶，一個字都不要改。\n"
        f"- 總長度控制在 {cap} 字元內；若超過，合併或提煉舊條目（保留最關鍵、刪掉過時細節）。\n\n"
        f"現有記憶：\n{current or '（目前還沒有任何記憶）'}\n\n"
        f"這輪對話：\n對方說：{user_input}\n{who}回：{ai_response}\n\n"
        "請輸出「更新後的完整記憶內容」本身，不要任何解釋、前言或標題。"
    )


def _acceptable_rewrite(candidate: str, current: str, cap: int) -> bool:
    """整理 LLM 的輸出能不能落地。

    - 空的：模型判斷這輪沒東西可記（或整個失敗），不動檔案。
    - 跟現有一模一樣：寫了也是白寫。
    - 超過 cap 的 1.5 倍：模型沒守住長度指示，寧可丟掉這輪也不要讓檔案
      失控膨脹——注入是每輪都付的成本。
    """
    return bool(candidate) and candidate != current and len(candidate) < int(cap * 1.5)


async def _request_rewrite(
    base_url: str,
    model: str,
    prompt: str,
    api_key: str,
    extra_body: dict | None,
) -> str:
    """讓對話用的 LLM 產出「更新後的完整記憶」。回傳清乾淨的文字。

    - Authorization：api_key 非空且不是 'ollama' 佔位才帶（本機 Ollama 不吃 header）。
    - extra_body 原樣併入。漏掉它曾讓這個功能從未寫出任何記憶：conf 靠
      extra_body.reasoning_effort='none' 關掉 Qwen3.5 的思考模式，這條路徑沒抄到，
      每次整理都思考到超過 60 秒 timeout，然後被 fail-soft 靜默吞掉。
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "stream": False,
        **(extra_body or {}),
    }
    headers = (
        {"Authorization": f"Bearer {api_key}"}
        if api_key and api_key != "ollama"
        else None
    )
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        text = r.json()["choices"][0]["message"]["content"]
    # 模型偶爾把整份輸出包在反引號裡
    return str(text).strip().strip("`").strip()


# --- 併發（同一段對話一次只整理一份）--------------------------------------

_consolidation_locks: "OrderedDict[tuple[str, str], asyncio.Lock]" = OrderedDict()
_MAX_LOCKS = 64


def _consolidation_lock(conf_uid: str, history_uid: str) -> asyncio.Lock:
    """同一段對話的整理必須排隊。

    整理是「讀出整份記憶 → 丟給 LLM 重寫 → 整份覆寫」，中間那步要花到 60 秒。
    沒有鎖的話，第 N 輪還在等 LLM、第 N+1 輪就開始了：兩邊各自讀到同一份舊記憶
    當底稿，各自整份寫回，後寫的贏——先寫那輪的新事實就這樣消失，而且不留痕跡
    （整條路徑是 fire-and-forget，失敗只記 warning）。本地慢模型加上
    memory_consolidation_interval=1 時這是搆得到的，不是理論風險。

    鎖要含蓋「讀」才有用：只鎖寫入的話兩邊依然是從同一份底稿長出來的。

    鎖以 (conf_uid, history_uid) 為單位——不同對話之間本來就互不相干，
    沒有理由讓它們互相等。
    """
    key = (str(conf_uid), str(history_uid))
    lock = _consolidation_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _consolidation_locks[key] = lock
    _consolidation_locks.move_to_end(key)

    # 長時間執行不該讓這張表無限長。只淘汰沒被持有的鎖——把還鎖著的鎖丟掉，
    # 等於讓下一輪拿到一把新鎖，併發保護就破了。
    excess = len(_consolidation_locks) - _MAX_LOCKS
    if excess > 0:
        stale = [k for k, v in _consolidation_locks.items() if not v.locked()]
        for old_key in stale[:excess]:
            _consolidation_locks.pop(old_key, None)
    return lock


async def consolidate_core_memory(
    conf_uid: str,
    history_uid: str,
    user_input: str,
    ai_response: str,
    base_url: str,
    model: str,
    cap: int = CAP_CHARS,
    api_key: str = "",
    extra_body: dict | None = None,
    character_name: str = "",
) -> None:
    """一輪對話結束後背景執行：值得記的才更新 core_memory.md。

    fire-and-forget——任何失敗只記 warning，絕不影響對話本身。
    """
    try:
        if not history_uid:
            return
        if not user_input or not user_input.strip():
            return

        limit = _clamp_cap(cap)
        # 讀→重寫→寫回，整段持鎖。見 _consolidation_lock。
        async with _consolidation_lock(conf_uid, history_uid):
            current = load_core_memory(conf_uid, history_uid)
            prompt = build_consolidation_prompt(
                current=current,
                user_input=user_input,
                ai_response=ai_response,
                cap=limit,
                character_name=character_name,
            )
            candidate = await _request_rewrite(
                base_url, model, prompt, api_key, extra_body
            )
            if _acceptable_rewrite(candidate, current, limit):
                _write_memory(conf_uid, history_uid, candidate)
                logger.info(
                    f"[core_memory] updated for {conf_uid}/{history_uid} "
                    f"({len(candidate)} chars)"
                )
    except Exception as e:
        logger.warning(
            f"[core_memory] consolidate failed for {conf_uid}/{history_uid}: {e}"
        )


def resolve_consolidation_llm(character_config: Any) -> tuple[str, str, str, dict]:
    """Return the OpenAI-compatible endpoint used by the active conversation LLM.

    Memory consolidation is part of the active conversation pipeline, so it must
    follow ``basic_memory_agent.llm_provider`` instead of silently hard-coding the
    ``openai_compatible_llm`` block.  LM Studio, Ollama and the other compatible
    providers expose the same base_url/model/key leaves.
    """
    agent_config = character_config.agent_config
    provider = agent_config.agent_settings.basic_memory_agent.llm_provider
    llm_config = getattr(agent_config.llm_configs, provider, None)
    if llm_config is None:
        raise ValueError(f"Active LLM provider config not found: {provider}")

    base_url = str(getattr(llm_config, "base_url", "") or "").strip()
    model = str(getattr(llm_config, "model", "") or "").strip()
    api_key = str(getattr(llm_config, "llm_api_key", "") or "")
    if not base_url or not model:
        raise ValueError(
            f"Active LLM provider {provider} is not OpenAI-compatible for memory consolidation"
        )
    # extra_body 必須跟著走：對話快是因為它關掉思考模式，整理沒帶就會 timeout。
    extra_body = getattr(llm_config, "extra_body", None) or {}
    return base_url, model, api_key, dict(extra_body)
