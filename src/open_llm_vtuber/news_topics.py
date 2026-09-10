"""主動話題的素材來源：抓新聞標題，組成她主動開口時看的提示詞。

她主動說話用的 prompts/utils/proactive_speak_prompt.txt 是後端每次觸發都重讀的
（prompt_loader.load_util，沒有快取），所以這裡直接覆寫那個檔——下一次觸發就生效，
不必重啟。

純標準庫（urllib + ElementTree）從 Google News RSS 抓，不用 LLM、不裝套件。所以
player LLM 不需要具備網路搜尋能力也能聊到今天的事。

行為契約由 tests/test_news_topics_behavior.py 釘住。

搬進套件的理由：早期版本住在 scripts/ 而 scripts/ 不是套件，topics_route 只好用
importlib.util 按檔案路徑載入、測試則要 sys.path.insert。現在它就是個普通模組，
兩個 hack 都不需要了；scripts/news_topics.py 留成薄殼，舊的 cron 設定照常可用。
"""

from __future__ import annotations

import datetime
import html
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from loguru import logger

# --- 位置 --------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = str(_ROOT / "prompts" / "utils" / "proactive_speak_prompt.txt")
# 端出過的標題，用來避免同一則時事一直重複端給她。
SEEN_PATH = str(_ROOT / "prompts" / "utils" / "seen_news.json")

# --- 調節參數 ----------------------------------------------------------------

SEEN_MAX = 500  # seen 最多保留幾筆（超過淘汰最舊）
SEEN_TTL_DAYS = 14  # 超過幾天的記錄淘汰
PER_CAT = 4  # 每個主題取幾則
_FETCH_BUFFER = 8  # 多抓幾則當緩衝，被 seen 濾掉一批後仍湊得齊
_TIMEOUT_SECONDS = 15

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_RSS_ENDPOINT = "https://news.google.com/rss/search"
# Google News 用「標題 - 來源」或「標題 | 來源」的格式，去掉尾綴她念起來才自然。
_SOURCE_SEPARATORS = (" - ", " | ")

# 主題 → 更好的 Google News 查詢字。UI 沒有固定分類勾選，這只是「精選關鍵字」的
# 查詢提示；沒列在這裡的主題字串會直接拿去查。topics_route 透過 import 取用。
CATEGORIES: list[tuple[str, str]] = [
    ("國際", "國際 新聞"),
    ("台灣", "台灣"),
    ("財經", "財經 股市"),
    ("科技", "科技"),
    ("AI", "AI 人工智慧"),
    ("科學", "科學"),
    ("動漫", "動漫 新番"),
    ("電玩", "電玩 遊戲"),
    ("娛樂", "娛樂"),
    ("電影", "電影"),
    ("音樂", "音樂"),
    ("體育", "體育"),
    ("健康", "健康"),
    ("生活", "生活"),
    ("美食", "美食"),
    ("旅遊", "旅遊"),
    ("汽車", "汽車"),
    ("時尚", "時尚"),
]


# --- 標題正規化 ---------------------------------------------------------------


def normalize_title(title) -> str:
    """把標題化成穩定的比對鍵：解 HTML 實體、去掉來源尾綴。

    抓取端本來就會去尾綴，這裡再做一次，讓帶尾綴與不帶尾綴的寫法都比得到——
    舊的 seen 檔裡可能兩種都有。
    """
    text = html.unescape(str(title or "")).strip()
    for sep in _SOURCE_SEPARATORS:
        if sep in text:
            text = text.rsplit(sep, 1)[0].strip()
    return text


# --- 端過的標題（跨輪去重）-----------------------------------------------------


def _now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


def _parse_timestamp(value) -> datetime.datetime | None:
    """把 ISO 時間戳讀回來；讀不懂就回 None（呼叫端當「不知道多舊」處理）。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        return None


def _prune_seen(seen: dict) -> dict:
    """汰舊：先丟掉過期的，再把總數壓到上限（留最新的）。

    時間戳壞掉或缺漏的條目視為「現在」保留——它可能是剛寫進去的，砍掉會讓那則
    新聞馬上又被端一次。下次寫回時會補上正常時間戳。
    """
    if not seen:
        return {}

    now = _now()
    cutoff = now - datetime.timedelta(days=SEEN_TTL_DAYS)
    fallback = now.isoformat(timespec="seconds")

    kept: dict[str, str] = {}
    for title, stamp in seen.items():
        when = _parse_timestamp(stamp)
        if when is not None and when < cutoff:
            continue
        kept[title] = stamp if _parse_timestamp(stamp) else fallback

    if len(kept) <= SEEN_MAX:
        return kept

    newest_first = sorted(
        kept.items(),
        key=lambda item: _parse_timestamp(item[1]) or now,
        reverse=True,
    )
    return dict(newest_first[:SEEN_MAX])


def load_seen() -> dict:
    """讀端過的標題記錄，回傳 {正規化標題: ISO 時間戳}，順便汰舊。

    fail-soft：檔案不存在、壞掉、格式不對，一律當空的——壞檔不可以卡住抓新聞。
    """
    raw: dict[str, str] = {}
    try:
        path = Path(SEEN_PATH)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                raw = {
                    k: (v if isinstance(v, str) else "")
                    for k, v in data.items()
                    if isinstance(k, str) and k.strip()
                }
    except Exception as e:
        logger.warning(f"[news] seen_news.json unreadable, treating as empty: {e}")
        raw = {}
    return _prune_seen(raw)


def save_seen(seen: dict) -> None:
    """原子寫回 seen 記錄。"""
    path = Path(SEEN_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(_prune_seen(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def mark_seen(seen: dict, titles) -> dict:
    """把這輪真的端出去的標題記進 seen。就地修改並回傳同一個 dict。"""
    stamp = _now().isoformat(timespec="seconds")
    for title in titles or []:
        key = normalize_title(title)
        if key:
            seen[key] = stamp
    return seen


# --- 抓取 --------------------------------------------------------------------


def _rss_url(query: str) -> str:
    params = urllib.parse.urlencode(
        {"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"}
    )
    return f"{_RSS_ENDPOINT}?{params}"


def fetch_titles(query: str, limit: int) -> list[str]:
    """查一個關鍵字，回傳去過尾綴、去過重的標題（最多 limit 筆）。"""
    request = urllib.request.Request(_rss_url(query), headers={"User-Agent": _UA})
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        payload = response.read()

    titles: list[str] = []
    for item in ET.fromstring(payload).iterfind(".//item"):
        title = normalize_title(item.findtext("title"))
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def _seen_keys(seen) -> set[str]:
    """把呼叫端給的 seen（dict／set／list／None）化成一組比對用的鍵。"""
    if isinstance(seen, dict):
        source = seen.keys()
    elif isinstance(seen, (set, list, tuple)):
        source = seen
    else:
        return set()
    return {normalize_title(k) for k in source}


def fetch_news_blocks(
    categories=None,
    per_cat: int = PER_CAT,
    seen=None,
    new_titles=None,
) -> tuple[list[str], bool]:
    """抓每個主題的新聞，回傳 (區塊清單, 有沒有抓到東西)。

    區塊長這樣：``主題：\\n- 標題\\n- 標題``。

    去重有兩層：本輪跨主題（同一則不會出現在兩個主題底下），以及跨輪——``seen``
    裡出現過的標題不再端出。``new_titles`` 傳入 list 時，這輪真的端出去的標題會
    append 進去，讓呼叫端寫回 seen。

    任何一個主題抓失敗只略過那一個，其他照抓——一個壞掉的查詢不該讓她整晚沒話題。
    """
    if categories is None:
        categories = CATEGORIES

    already_served = _seen_keys(seen)
    served_this_round: set[str] = set()
    blocks: list[str] = []

    for label, query in categories:
        try:
            candidates = fetch_titles(query, per_cat + _FETCH_BUFFER)
        except Exception as e:
            logger.warning(f"[news] fetch failed for {label}: {e}")
            continue

        picked: list[str] = []
        for title in candidates:
            key = normalize_title(title)
            if not key or key in served_this_round:
                continue
            served_this_round.add(key)
            if key in already_served:
                continue
            picked.append(title)
            if isinstance(new_titles, list):
                new_titles.append(title)
            if len(picked) >= per_cat:
                break

        if picked:
            lines = "\n".join(f"- {t}" for t in picked)
            blocks.append(f"{label}：\n{lines}")

    return blocks, bool(blocks)


# --- 組裝與寫檔 ---------------------------------------------------------------

# 主動開口時她看到的指示。這段文字直接決定她開場的樣子，所以每一條都是實測
# 過的——底下註記的行為都真的發生過。
#
# 全文用「對方」而不是「使用者」：人設裡沒有「使用者」這個概念，那是系統的詞，
# 而且已經漏進台詞過（有角色說過「你是……能自由與我交談的物件」）。
INSTRUCTION = """對方已經有一段時間沒講話了。請你（這個角色）自然地開口。

這一輪對方沒有說話，你不是在回覆誰。他上一則訊息你早就回過了，不要再回一次，
也不要用「你這樣說」「既然你這麼說」這種回應語氣起手。

三個選擇一樣合理，挑此刻最自然的那個。不要每次都選第一個：

一、延續剛才那件事——前提是它真的還有沒講完的話題、問題或情緒。沿著它補一個新
　　觀點或追問，不要重述已經講過的。
二、換一個新話題——剛才那件事講完了、你剛拒絕了對方的要求、或話題以玩笑收尾
　　時，換題最自然。第一句就直接講新的那件事，不要宣告「那我們換個話題」，
　　也不要回顧或收尾前一個。
三、直接跟對方搭話——叫他一聲、說你此刻的念頭或狀態、或問他正在做什麼。

**不要把選項混著用**：延續前一件事的結尾又補一句不相干的新問句，是最常見的錯誤
——聽起來像兩個人在講話。

其他幾條：

- 一次只談一件事，最多問一個問題。上一次主動開口如果問過問題，這次就不要再問，
  改說你自己的具體觀察或看法——連著問會變成訪談。
- 不要像念稿或報新聞。不要問「最近有什麼新鮮事」「工作還順利嗎」「有什麼想聊的
  嗎」這種空問句。
- 你是在陪對方聊天，不是在寫產品建議。不要用「系統偵測」「用戶正在」這種第三
  人稱的教學口吻。
- 分清楚誰是誰：對方用「我」講過的經歷與感受，你要用「你」承接，不能寫成自己
  做過或感受到。
- 不要承諾「我會改進」，不要問「有什麼可以幫你」，也不要把找話題的責任丟回去。
- 長度不限，但要前後連貫、帶進新的具體內容，不要重複同一個觀點湊長度。
- 不要說明你在主動開口，也不要提到話題清單、新聞或任何機制。直接把話講出來。"""


def compose_content(manual_topics=None, news_blocks=None, got_any: bool = False) -> str:
    """組出要寫進 proactive_speak_prompt.txt 的完整內容。

    統一話題模型：manual_topics 是唯一一份「主動話題」清單，同時驅動兩種模式——
      - 新聞關閉：只附這份話題清單（她從自己的知識聊起，不抓網路）。
      - 新聞開啟：每個話題各抓一則 Google News，news_blocks 帶進「最近的新聞」區塊。
    兩種模式用的是同一份清單，差別只在 news_blocks 有沒有東西。

    一律保留人設指示（INSTRUCTION）開頭——這是「別像念稿/別提機制」的護欄，不能掉。
    話題清單非空 -> 附「你可以聊的主題」區塊。
    新聞有抓到（got_any 且 news_blocks 非空）-> 附「最近的新聞」區塊。
    都沒有 -> 只回人設指示（永不留下壞檔，鏡像舊 main() 全失敗分支）。
    """
    manual_topics = manual_topics or []
    news_blocks = news_blocks or []

    parts = [INSTRUCTION]

    manual_clean = [str(t).strip() for t in manual_topics if str(t).strip()]
    has_list = bool(manual_clean) or bool(got_any and news_blocks)

    # 「從下面的主題或新聞挑一則」只有在下面真的有清單時才說得通。清單是空的還
    # 這樣寫，等於叫模型從不存在的東西裡選題——它只好自己編，編出來的就是
    # 「你最近有聽過哪首曲子嗎？」這種丟回給使用者的萬用問句。
    if has_list:
        parts.append("想換題的話，可以從下面的主題或新聞挑一則自然聊起。")
    else:
        parts.append(
            "這次沒有預先準備的主題清單。不必硬找話題——講一件此刻具體的小事、"
            "一個你正在想的念頭，或畫面裡真的看得到的東西就夠了。寧可短，"
            "也不要為了湊出話題而問一句空泛的問句。"
        )

    if manual_clean:
        topic_lines = "\n".join(f"- {t}" for t in manual_clean)
        parts.append(
            "【你可以聊的主題——挑一個聊起來就好，不必提到其他】\n" + topic_lines
        )

    if got_any and news_blocks:
        news = "\n\n".join(news_blocks)
        parts.append(
            "【今天的新聞——只是素材，挑一則聊起來就好，不必提到其他】\n" + news
        )

    return "\n\n".join(parts) + "\n"


def write_prompt(content: str) -> None:
    """原子寫入 proactive_speak_prompt.txt（temp + os.replace）。

    她每次主動說話都會重讀這個檔，寫到一半被中斷會留下半截的壞檔。
    """
    path = Path(PROMPT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def refresh_from_news() -> tuple[int, int]:
    """抓一輪新聞、覆寫提示詞。回傳 (寫入字元數, 這輪新端出的標題數)。

    只有真的端出新標題才寫回 seen——全部抓失敗或全被過濾時不動記錄，否則
    下一輪會以為這些都端過了。
    """
    seen = load_seen()
    new_titles: list[str] = []
    blocks, got_any = fetch_news_blocks(seen=seen, new_titles=new_titles)
    content = compose_content(manual_topics=None, news_blocks=blocks, got_any=got_any)
    write_prompt(content)

    if new_titles:
        try:
            save_seen(mark_seen(seen, new_titles))
        except Exception as e:
            # seen 寫失敗不該讓已經寫好的提示詞白費。
            logger.warning(f"[news] save_seen failed: {e}")

    logger.info(
        f"[news] wrote {PROMPT_PATH} ({len(content)} chars, "
        f"news={got_any}, new={len(new_titles)})"
    )
    return len(content), len(new_titles)
