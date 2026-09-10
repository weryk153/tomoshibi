"""角色管理：新增、編輯、刪除陪伴角色，不必碰 YAML。

一個「角色」就是 characters/ 底下一個帶 character_config 區塊的檔案。切換角色時
它會深度合併到 conf.yaml 之上——沒寫的欄位沿用底稿。真正的切換動作走 WebSocket
（switch-config），這裡只負責管檔案。

三個約束是彼此牽連的，改動任何一個之前要先理解：

- **conf_uid 就是檔名主幹，而且編輯時不可更動。** 記憶存在
  chat_history/<conf_uid>/<history_uid>/core_memory.md，改掉 conf_uid 等於讓
  那個角色底下每一段對話的記憶都變成孤兒——她會突然什麼都不記得，而檔案還在
  硬碟上沒人認領。
- **檔名一律是 ASCII slug**（mili.yaml），中文顯示名字放在 conf_name。這樣可以
  完全避開網址與路徑組合的邊界情況。
- **底稿 conf.yaml 在這裡是唯讀的。** 角色檔是我們自己產生的，沒有使用者寫的
  註解要保護，所以整份用 ruamel 序列化就好；conf.yaml 不一樣，它有滿滿的註解，
  絕不從這裡改寫。

寫入一律「先寫暫存檔再 os.replace」，避免存到一半斷電留下半個角色。
"""

import os
import re
import json
import uuid
import glob
import shutil
from pathlib import Path
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from loguru import logger

from .api_guard import (
    forbidden as _forbidden,
    is_trusted_request as _is_local_request,
    make_yaml as _make_yaml,
)
from .conf_editor import write_conf_document
from .config_manager.utils import read_yaml
from .utils.path_safety import safe_join


# --- 位置 ------------------------------------------------------------------- #

CONF_PATH = "conf.yaml"
CHARACTERS_DIR = "characters"
LIVE2D_DIR = "live2d-models"
MODEL_DICT_PATH = "model_dict.json"
MODEL_DICT_DEFAULT_PATH = "config_templates/model_dict.default.json"
AVATARS_DIR = "avatars"

# 檔名只用 ASCII，網址與路徑組合才不會踩到編碼的邊界情況。
SLUG_RE = re.compile(r"^[a-z0-9_-]{1,40}$")

# --- 圖片上傳 --------------------------------------------------------------- #
#
# 兩種上傳共用同一套規則：先看副檔名、再看解碼後的大小。兩道都要，因為附檔名
# 是使用者說了算的，而真正會塞爆硬碟的是解碼後的位元組。
#
# 允許的類型跟服務端對齊：server.py 的 AvatarStaticFiles 會 403 掉清單以外的
# 東西，背景則要跟 scan_bg_directory() 掃得到的副檔名一致，否則上傳成功卻不會
# 出現在選單裡。

AVATAR_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"}
# data URL 上傳走的是 MIME，對回副檔名讓存下來的檔名可預期。
AVATAR_MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}
AVATAR_MAX_BYTES = 4 * 1024 * 1024

BG_DIR = "backgrounds"
# 背景不收 svg／webp——scan_bg_directory 掃不到，收了會變成「存好了但看不到」。
BG_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif"}
# 背景是全螢幕的，給比頭像寬鬆的上限。
BG_MAX_BYTES = 12 * 1024 * 1024

# 找 .model3.json 時往下挖幾層就好，不做無底洞的遞迴。
MODEL3_GLOB_DEPTHS = ("*.model3.json", "*/*.model3.json", "*/*/*.model3.json")


# --- 檔名（slug）----------------------------------------------------------- #


def _slugify(raw: str) -> str:
    """把任意字串壓成合法檔名：只留 [a-z0-9_-]，空白換成底線。

    全中文的名字會被壓成空字串——那是預期內的，呼叫端會退回產生的識別碼。
    截到 40 字元，免得檔名長到難以處理。
    """
    text = re.sub(r"[^a-z0-9_-]", "", str(raw or "").strip().lower().replace(" ", "_"))
    return text.strip("_-")[:40]


def _derive_slug(requested: Optional[str], conf_name: str) -> str:
    """決定用哪個 slug：使用者指定的優先，其次由顯示名產生，都不行就給隨機碼。"""
    for candidate in (requested, conf_name):
        slug = _slugify(candidate or "")
        if slug and SLUG_RE.match(slug):
            return slug
    return "char_" + uuid.uuid4().hex[:8]


def _conf_uid_of(path: str) -> Optional[str]:
    """讀一個設定檔的 conf_uid；讀不到（壞檔、缺欄位）回 None。"""
    try:
        data = read_yaml(path) or {}
        uid = (data.get("character_config") or {}).get("conf_uid")
        return str(uid) if uid else None
    except Exception:
        # 容忍單一壞檔——一個人手改壞的角色不該讓整份清單失敗。
        return None


def _existing_conf_uids(exclude_filename: Optional[str] = None) -> set:
    """目前用掉的 conf_uid，含底稿與每一個角色檔。"""
    paths = [CONF_PATH] + [
        p
        for p in _list_character_files()
        if not (exclude_filename and os.path.basename(p) == exclude_filename)
    ]
    return {uid for uid in map(_conf_uid_of, paths) if uid}


def _unique_slug(slug: str, taken_uids: set) -> str:
    """確保 slug 不會撞到既有的檔案或 conf_uid，撞到就加序號。

    兩種衝突都要看：檔案已經存在，或那個 uid 已經被別人用了。只看其中一種的話，
    會做出一個檔名沒撞但記憶跟別人共用的角色。
    """

    def taken(candidate: str) -> bool:
        if candidate in taken_uids:
            return True
        # 探測硬碟之前先確認這個 slug 組得出安全路徑。組不出來的（含 .. 或
        # 分隔符）當成衝突，換一個候選。
        safe = _safe_character_path(f"{candidate}.yaml")
        return safe is None or os.path.exists(safe)

    if not taken(slug):
        return slug
    for i in range(2, 1000):
        candidate = f"{slug}_{i}"[:40]
        if not taken(candidate):
            return candidate
    return "char_" + uuid.uuid4().hex[:8]


# --- 路徑守衛 --------------------------------------------------------------- #


def _safe_character_path(filename: str) -> Optional[str]:
    """把檔名解析成 characters/ 底下的路徑，逃出去就回 None。

    filename 是使用者送來的（PUT/DELETE 的路徑參數），所以三道都要過：不可以是
    conf.yaml、必須是不含任何分隔符的純檔名、必須以 .yaml 結尾。最後再交給
    safe_join 擋掉符號連結之類的花樣。
    """
    if not filename or filename == CONF_PATH:
        return None
    if os.path.basename(filename) != filename or not filename.endswith(".yaml"):
        return None
    try:
        return safe_join(CHARACTERS_DIR, filename)
    except ValueError:
        return None


def _list_character_files() -> list:
    """characters/ 底下所有的 .yaml。"""
    if not os.path.isdir(CHARACTERS_DIR):
        return []
    return [
        os.path.join(root, name)
        for root, _, names in os.walk(CHARACTERS_DIR)
        for name in names
        if name.endswith(".yaml")
    ]


# --- model_dict.json ------------------------------------------------------- #
#
# 這份清單記錄每個 Live2D 模型的顯示設定（縮放、位移、表情對照）。
# live2d_config_route 掃描到新模型時會登記進來，這裡提供讀寫。


def _find_model3(model_dir: str) -> Optional[str]:
    """在模型資料夾裡找出 .model3.json；限定深度，不做無底洞的遞迴。"""
    for pattern in MODEL3_GLOB_DEPTHS:
        matches = sorted(glob.glob(os.path.join(model_dir, pattern)))
        if matches:
            return matches[0]
    return None


def _ensure_model_dict() -> None:
    """首次執行時，把隨附的預設複製成使用者的 model_dict.json。

    跟 conf.yaml 同一個模式。model_dict.json 是可變的使用者狀態——
    live2d_config_route 會在使用者設定動作對應與點擊區時改寫它——所以它不進
    版控；進版控的是 config_templates/model_dict.default.json。

    已經有使用者的那份就什麼都不做：使用者的設定永遠優先於預設。
    """
    if os.path.exists(MODEL_DICT_PATH) or not os.path.exists(MODEL_DICT_DEFAULT_PATH):
        return
    try:
        shutil.copy(MODEL_DICT_DEFAULT_PATH, MODEL_DICT_PATH)
        logger.info(
            f"[character] {MODEL_DICT_PATH} not found — created it from "
            f"{MODEL_DICT_DEFAULT_PATH} (first run)."
        )
    except OSError as e:
        # 複製不成不該擋住啟動：下面照樣回空清單，使用者仍能在 UI 裡加模型。
        logger.warning(
            f"[character] could not seed {MODEL_DICT_PATH}: {type(e).__name__}: {e}"
        )


def _load_model_dict() -> list:
    """讀 model_dict.json；不存在或壞掉都回空清單。"""
    _ensure_model_dict()
    if not os.path.exists(MODEL_DICT_PATH):
        return []
    try:
        with open(MODEL_DICT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"[character] model_dict.json read failed: {type(e).__name__}")
        return []


def _write_model_dict_atomic(entries: list) -> None:
    """原子寫入 model_dict.json。

    ensure_ascii=False：模型的顯示名稱可能是中文，跳脫成 unicode 逃逸碼之後人就看不懂
    了，而這個檔案是使用者有可能打開來看的。
    """
    path = Path(MODEL_DICT_PATH)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(
        json.dumps(entries, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


# --- 角色檔的讀寫 ----------------------------------------------------------- #


def _dig(data: dict, *keys: str, default=None):
    """一層一層往下取值，任何一層不是 dict 或不存在都回 default。

    角色檔是使用者手寫的，中間任何一層都可能缺、也可能被寫成純量。三個欄位
    原本各自包一個 try/except AttributeError，那是在用例外處理正常情況。
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _read_character_fields(path: str, *, is_base: bool) -> Optional[dict]:
    """讀一個角色設定檔，取出可編輯的欄位；讀不到回 None。"""
    try:
        data = read_yaml(path) or {}
    except Exception as e:
        logger.warning(f"[character] 跳過讀不了的角色檔 {path}：{type(e).__name__}")
        return None

    cc = data.get("character_config") or {}
    filename = os.path.basename(path)
    slug = None if is_base else filename.removesuffix(".yaml")

    return {
        "filename": filename,
        "slug": slug,
        "is_base": is_base,
        "conf_name": cc.get("conf_name"),
        "character_name": cc.get("character_name"),
        "avatar": cc.get("avatar"),
        "conf_uid": cc.get("conf_uid"),
        "live2d_model_name": cc.get("live2d_model_name"),
        "persona_prompt": cc.get("persona_prompt"),
        "voice": _dig(cc, "tts_config", "edge_tts", "voice"),
        # 回覆語言（R）是她用什麼語言想事情、寫回覆；語音語言（V）是用什麼語言
        # 發聲。兩者相同時語音路徑會跳過翻譯。留空＝沿用全域預設。
        "reply_language": cc.get("reply_language") or "",
        # 語音語言埋在 gpt_sovits_tts 底下——只有這個引擎有 text_lang。
        "voice_lang": _dig(cc, "tts_config", "gpt_sovits_tts", "text_lang", default=""),
        # 「用誰的聲音」三件套，同樣住在 gpt_sovits_tts 底下。GPT-SoVITS 是
        # zero-shot 克隆：聲線完全由 ref_audio_path 這段參考音決定，prompt_text
        # 是那段音檔的逐字稿、prompt_lang 是它的語言。三者是一組，逐字稿給錯
        # 音色就會歪。
        #
        # 這三個欄位原本只在「設定→語音合成」那頁有，而那頁寫的是 conf.yaml
        # 的全域值——於是角色面板選了 gpt_sovits_tts 卻沒有任何地方能挑聲音，
        # 每個角色都共用同一把嗓子。
        "ref_audio_path": _dig(
            cc, "tts_config", "gpt_sovits_tts", "ref_audio_path", default=""
        ),
        "prompt_text": _dig(
            cc, "tts_config", "gpt_sovits_tts", "prompt_text", default=""
        ),
        "prompt_lang": _dig(
            cc, "tts_config", "gpt_sovits_tts", "prompt_lang", default=""
        ),
        # 這個角色釘了哪個 TTS 引擎。空＝沒釘，沿用 conf.yaml 的 tts_model。
        #
        # 這個欄位曾經完全沒被讀出來，於是 UI 不知道角色檔裡有覆寫，而寫入端又
        # 無條件寫成 edge_tts——使用者在角色面板存一次檔，訓練好的音色就被打回
        # 內建語音，畫面上沒有任何線索。讀得到才寫得回去。
        "tts_model": _dig(cc, "tts_config", "tts_model", default=""),
    }


def _build_character_config(
    *,
    conf_name: str,
    conf_uid: str,
    persona_prompt: str,
    live2d_model_name: str,
    voice: Optional[str],
    character_name: Optional[str],
    avatar: Optional[str],
    reply_language: Optional[str] = None,
    voice_lang: Optional[str] = None,
    tts_model: Optional[str] = None,
    ref_audio_path: Optional[str] = None,
    prompt_text: Optional[str] = None,
    prompt_lang: Optional[str] = None,
) -> dict:
    """組出角色管理擁有的那幾個欄位。

    只寫這些；agent／llm／asr／vad 全部靠切換時的深度合併從底稿繼承。**沒設的
    欄位就不要寫出來**——寫一個空值會蓋掉底稿的設定，那跟「沿用預設」是相反的
    意思。
    """
    cc: dict = {
        "conf_name": conf_name,
        "conf_uid": conf_uid,
        "live2d_model_name": live2d_model_name,
        "persona_prompt": persona_prompt,
        # 顯示名一定要寫。不寫的話深度合併會讓她繼承底稿的名字——新建一個
        # 「日和」卻在對話框上顯示底稿角色的名字。UI 不一定會送這個欄位，
        # 所以退回 conf_name。
        "character_name": character_name or conf_name,
    }
    if avatar:
        cc["avatar"] = avatar
    # 選了 edge 語音就把語音記下來，但**不要**順手把 tts_model 釘成 edge_tts。
    # 以前這裡寫死 "tts_model": "edge_tts"，於是任何一次帶著 voice 的存檔都會
    # 把角色從 gpt_sovits 打回內建語音——使用者的說法是「一直被切回去」。
    # 引擎由下面的 tts_model 分支單獨決定，voice 只負責 edge_tts 的音色。
    if voice:
        tts = cc.setdefault("tts_config", {})
        tts["edge_tts"] = {"voice": voice}
    # 語言是角色自己的事：紅莉栖是日本人、貓娘不是。留空就不寫這個鍵，角色
    # 沿用全域預設（system_config.player_language）。
    if reply_language:
        cc["reply_language"] = reply_language
    # 語音語言（V）住在 gpt_sovits_tts 底下。這裡用 setdefault 疊上去而不是整個
    # 覆寫 tts_config——上面的 voice 分支可能已經寫了 edge_tts，兩者要並存。
    if voice_lang:
        tts = cc.setdefault("tts_config", {})
        tts.setdefault("gpt_sovits_tts", {})["text_lang"] = voice_lang
    # 參考音三件套跟 voice_lang 同住 gpt_sovits_tts，一樣用 setdefault 疊上去。
    # 每個都各自判斷有沒有值：使用者可能只想換聲音、不動語言。
    for key, value in (
        ("ref_audio_path", ref_audio_path),
        ("prompt_text", prompt_text),
        ("prompt_lang", prompt_lang),
    ):
        if value:
            tts = cc.setdefault("tts_config", {})
            tts.setdefault("gpt_sovits_tts", {})[key] = value
    # 引擎：留空＝不釘，角色沿用 conf.yaml 的 tts_model（deep_merge 時繼承）。
    # 這是唯一會寫 tts_config.tts_model 的地方。
    if tts_model:
        cc.setdefault("tts_config", {})["tts_model"] = tts_model
    return cc


def _write_character_yaml(path: str, character_config: dict) -> None:
    """把角色設定寫成一個角色檔（原子寫入）。

    角色檔是我們自己產生的，沒有使用者寫的註解要保護，所以整份 ruamel dump 就好
    ——這跟 conf.yaml 完全相反，那邊只能就地改行。

    allow_unicode 讓中文名字維持可讀，不要被跳脫成一串逃逸碼。
    """
    yaml = _make_yaml()
    yaml.allow_unicode = True

    # 人設通常是多行的，用 literal block scalar 存，使用者打開檔案還看得懂、
    # 也改得動；預設的折疊寫法會把它擠成一長串。
    from ruamel.yaml.scalarstring import LiteralScalarString

    cc = dict(character_config)
    persona = cc.get("persona_prompt")
    if isinstance(persona, str):
        # ensure trailing newline so ruamel emits a clean '|' block
        cc["persona_prompt"] = LiteralScalarString(
            persona if persona.endswith("\n") else persona + "\n"
        )

    payload = {"character_config": cc}

    conf_dir = os.path.dirname(os.path.abspath(path)) or "."
    tmp_path = os.path.join(conf_dir, "." + os.path.basename(path) + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f)
    os.replace(tmp_path, path)


def _set_or_clear(container: dict, key: str, value: Optional[str]) -> None:
    """三態語意：None＝這次沒要改，空字串＝明確清掉，有值＝設定。

    「清掉」這一態不能省。沒有它，使用者設過一次語言之後就再也回不去「沿用
    全域預設」——那個設定會變成單向的門。
    """
    if value is None:
        return
    if value:
        container[key] = value
    else:
        container.pop(key, None)


def _tts_leaf(cc: dict, *path: str) -> dict:
    """取得（必要時建立）tts_config 底下的巢狀容器。

    voice、voice_lang、tts_model 三個設定都住在 tts_config 底下的不同位置，各自
    可能先到也可能後到。原本每一個都自己寫一遍「不存在就建、存在就沿用」的
    巢狀判斷，三份都要記得不可以整個覆寫 tts_config——覆寫的話先設好的那個會被
    後設的那個抹掉。
    """
    node = cc.setdefault("tts_config", {})
    for key in path:
        node = node.setdefault(key, {})
    return node


def _update_base_character_config(
    *,
    conf_name: str,
    persona_prompt: str,
    live2d_model_name: str,
    voice: Optional[str],
    character_name: Optional[str],
    avatar: Optional[str],
    reply_language: Optional[str] = None,
    voice_lang: Optional[str] = None,
    tts_model: Optional[str] = None,
    ref_audio_path: Optional[str] = None,
    prompt_text: Optional[str] = None,
    prompt_lang: Optional[str] = None,
) -> None:
    """就地更新底稿 conf.yaml 的 character_config。

    跟角色檔不同：conf.yaml 滿是使用者手寫的註解，所以走 ruamel 的 round-trip
    載入（保留註解與結構），只改指定的葉節點，絕不重新序列化無關的區塊。
    """
    from ruamel.yaml.scalarstring import LiteralScalarString

    yaml = _make_yaml()
    yaml.allow_unicode = True
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    if data is None or "character_config" not in data:
        raise KeyError("character_config block not found in conf.yaml")
    cc = data["character_config"]

    cc["conf_name"] = conf_name
    cc["live2d_model_name"] = live2d_model_name
    # 顯示名一定要有，否則對話框上會出現底稿角色的名字。
    cc["character_name"] = character_name or conf_name

    # 人設是多行的，用 literal block scalar 存，使用者打開檔案還看得懂、也改得動。
    if isinstance(persona_prompt, str):
        text = (
            persona_prompt if persona_prompt.endswith("\n") else persona_prompt + "\n"
        )
        cc["persona_prompt"] = LiteralScalarString(text)
    else:
        cc["persona_prompt"] = persona_prompt

    # 頭像：明確給空字串＝清掉，None＝這次沒動到（保留硬碟上的值）。
    if avatar is not None:
        cc["avatar"] = avatar

    # 語音只在有給值時才碰，而且只碰 edge_tts.voice。
    #
    # 這裡以前在 tts_config 不存在時會順手補上 tts_model: edge_tts——於是選一次
    # 語音就把引擎釘死成內建語音，使用者訓練好的音色被打回去，而且畫面上沒有
    # 任何線索。引擎由下面的 tts_model 單獨決定。
    if voice:
        _tts_leaf(cc, "edge_tts")["voice"] = voice

    _set_or_clear(cc, "reply_language", reply_language)

    # 語音語言住在 gpt_sovits_tts 底下——只有那個引擎有 text_lang。
    if voice_lang is not None:
        if voice_lang:
            _tts_leaf(cc, "gpt_sovits_tts")["text_lang"] = voice_lang
        else:
            _dig(cc, "tts_config", "gpt_sovits_tts", default={}).pop("text_lang", None)

    # 參考音三件套跟 voice_lang 同一套規則：None（缺鍵）＝這次沒動，
    # ""＝清掉那個鍵，改回沿用 conf.yaml 的全域參考音。
    for key, value in (
        ("ref_audio_path", ref_audio_path),
        ("prompt_text", prompt_text),
        ("prompt_lang", prompt_lang),
    ):
        if value is None:
            continue
        if value:
            _tts_leaf(cc, "gpt_sovits_tts")[key] = value
        else:
            _dig(cc, "tts_config", "gpt_sovits_tts", default={}).pop(key, None)

    # 引擎：空字串＝改回沿用 conf.yaml 的全域設定。
    if tts_model is not None:
        if tts_model:
            cc.setdefault("tts_config", {})["tts_model"] = tts_model
        else:
            _dig(cc, "tts_config", default={}).pop("tts_model", None)

    write_conf_document(lambda f: yaml.dump(data, f))


# --- 請求解析 --------------------------------------------------------------- #


def _extract_body_fields(body: dict) -> dict:
    """把請求 body 正規化成欄位字典。

    同時接受完整名稱與簡寫（name／persona／skin／file）——前端歷來兩種都送過。

    **缺鍵與空字串是兩件事**，這裡刻意不合併：缺鍵＝這次沒有要改（維持原狀），
    空字串＝明確清掉（改回沿用全域或底稿）。合併的話使用者就再也沒辦法把一個
    設過的值改回「沿用預設」。
    """

    def text(*names: str):
        """取第一個有值的鍵，字串就去頭尾空白，非字串原樣回傳。"""
        for name in names:
            value = body.get(name)
            if value is not None:
                return value.strip() if isinstance(value, str) else value
        return None

    return {
        "conf_name": text("conf_name", "name"),
        # 人設不 strip：使用者刻意排版的縮排與空行是內容的一部分。
        "persona_prompt": body.get("persona_prompt", body.get("persona")),
        "live2d_model_name": text("live2d_model_name", "skin"),
        "voice": text("voice"),
        "slug": body.get("slug"),
        "character_name": body.get("character_name"),
        "avatar": text("avatar"),
        "reply_language": text("reply_language"),
        "voice_lang": text("voice_lang"),
        "tts_model": text("tts_model"),
        # 「用誰的聲音」——只對 gpt_sovits_tts 有意義。prompt_text 不 strip 掉
        # 內部空白，但頭尾的要去掉（text() 已經做了）：逐字稿要跟參考音對得上。
        "ref_audio_path": text("ref_audio_path"),
        "prompt_text": text("prompt_text"),
        "prompt_lang": text("prompt_lang"),
    }


def _bad_request(msg: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "error": msg})


# --- 圖片上傳的實作 --------------------------------------------------------- #


def _safe_avatar_filename(conf_uid: Optional[str], ext: str) -> str:
    """組出安全的頭像檔名：<slug 或隨機碼><副檔名>。

    The base is the slugified conf_uid when usable (so re-uploading for the same
    character overwrites instead of littering), else a random hex. ``ext`` is one
    of AVATAR_ALLOWED_EXTS and already includes the leading dot.
    """
    base = _slugify(conf_uid or "")
    if not base or not SLUG_RE.match(base):
        base = "char_" + uuid.uuid4().hex[:8]
    return f"{base}{ext}"


def _decode_data_url(data: str) -> Optional[tuple]:
    """把 data URL 解成 (位元組, 副檔名)；格式不對或類型不允許就回 None。

    Accepts only the image mimes in AVATAR_MIME_EXT. Tolerates a bare base64
    payload only when paired with a known extension elsewhere (not here) — a plain
    data-URL must carry its mime so we can pick a safe extension.
    """
    import base64

    if not isinstance(data, str) or not data.startswith("data:"):
        return None
    try:
        header, payload = data.split(",", 1)
    except ValueError:
        return None
    # header looks like "data:image/png;base64"
    meta = header[len("data:") :]
    mime = meta.split(";", 1)[0].strip().lower()
    ext = AVATAR_MIME_EXT.get(mime)
    if ext is None:
        return None
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception:
        return None
    if not raw or len(raw) > AVATAR_MAX_BYTES:
        return None
    return raw, ext


def _write_avatar_atomic(filename: str, raw: bytes) -> None:
    """把頭像寫進 avatars/（原子寫入）。"""
    os.makedirs(AVATARS_DIR, exist_ok=True)
    dest = os.path.join(AVATARS_DIR, filename)
    tmp_path = os.path.join(AVATARS_DIR, "." + filename + ".tmp")
    with open(tmp_path, "wb") as f:
        f.write(raw)
    os.replace(tmp_path, dest)


def _safe_bg_filename(orig_name: str, ext: str) -> str:
    """組出安全的背景檔名：<原檔名的 slug 或隨機碼>-<隨機碼><副檔名>。

    Always appends a short random suffix so an upload never overwrites a bundled
    background or a previous upload of the same name. ``ext`` includes the dot.
    """
    base = _slugify(os.path.splitext(orig_name or "")[0])
    if not base or not SLUG_RE.match(base):
        base = "bg"
    return f"{base}-{uuid.uuid4().hex[:6]}{ext}"


def _write_bg_atomic(filename: str, raw: bytes) -> None:
    """把背景圖寫進 backgrounds/（原子寫入）。"""
    os.makedirs(BG_DIR, exist_ok=True)
    dest = os.path.join(BG_DIR, filename)
    tmp_path = os.path.join(BG_DIR, "." + filename + ".tmp")
    with open(tmp_path, "wb") as f:
        f.write(raw)
    os.replace(tmp_path, dest)


# --------------------------------------------------------------------------- #
# Route factory
# --------------------------------------------------------------------------- #


def _rescan_skins() -> None:
    """掃描 live2d-models/ 並登記新模型。

    延遲 import：live2d_config_route 反向依賴這個模組（_find_model3、
    _load_model_dict 等），頂層互相 import 會繞成一圈。

    呼叫端把這件事包在 try/except 裡當成「盡力而為」——掃不到不該擋住建立角色。
    但那個 except 也曾經吞掉一個 NameError（函式搬家後忘了 import），掃描從此
    完全沒跑，而畫面顯示一切正常。所以這裡把它收成具名函式，讓「盡力而為」的
    範圍縮到真的只有掃描本身。
    """
    from .live2d_config_route import list_all_skins

    list_all_skins()


def init_character_route() -> APIRouter:
    """角色管理的端點。只接受可信來源。

    - GET    /api/characters          列出所有角色與可編輯的欄位
    - POST   /api/characters          新建一個角色檔
    - PUT    /api/characters/{檔名}    修改既有角色
    - DELETE /api/characters/{檔名}    刪除角色
    - POST   /api/character/avatar    上傳頭像，回傳存好的檔名
    - POST   /api/background          上傳背景圖

    PUT／DELETE 的檔名是使用者送來的路徑參數，一律先過 _safe_character_path。
    """
    router = APIRouter()

    # ------------------------------------------------------------------ #
    @router.get("/api/characters")
    async def list_characters(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        characters = []
        # base conf.yaml first
        base = _read_character_fields(CONF_PATH, is_base=True)
        if base is not None:
            characters.append(base)
        # then every override file
        for path in sorted(_list_character_files()):
            fields = _read_character_fields(path, is_base=False)
            if fields is not None:
                characters.append(fields)
        return JSONResponse({"characters": characters})

    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    @router.post("/api/characters")
    async def create_character(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            body = await request.json()
        except Exception:
            return _bad_request("Invalid JSON body.")
        if not isinstance(body, dict):
            return _bad_request("Invalid JSON body.")

        fields = _extract_body_fields(body)
        conf_name = fields["conf_name"]
        persona = fields["persona_prompt"]
        skin = fields["live2d_model_name"]
        voice = fields["voice"] or None

        if not conf_name:
            return _bad_request("Missing display name (conf_name).")
        if not persona or not str(persona).strip():
            return _bad_request("Missing persona_prompt.")
        if not skin:
            return _bad_request("Missing live2d_model_name (skin).")

        # 先掃描一次再驗證：使用者可能剛把模型資料夾丟進去。
        try:
            await asyncio.to_thread(_rescan_skins)
        except Exception as e:
            logger.warning(f"pre-create skin scan failed: {type(e).__name__}")
        registered = {m.get("name") for m in _load_model_dict()}
        if skin not in registered:
            return _bad_request(
                f"Skin '{skin}' is not a registered Live2D model. "
                "Drop it into live2d-models/ then rescan."
            )

        taken_uids = _existing_conf_uids()
        slug = _derive_slug(fields["slug"], conf_name)
        # 前端明確指定的檔名照用，撞名就回 409 讓它去問使用者。只有伺服器自己
        # 推導出來的檔名（例如全中文的名字）才自動加序號——那不是使用者選的名字，
        # 撞名時默默換一個比較好；使用者自己打的名字被偷偷改掉才是意外。
        client_slug = _slugify(fields["slug"] or "")
        client_supplied = bool(client_slug) and SLUG_RE.match(client_slug) is not None
        if not client_supplied:
            slug = _unique_slug(slug, taken_uids)
        filename = f"{slug}.yaml"
        path = _safe_character_path(filename)
        if path is None:
            return _bad_request("Could not derive a safe filename.")
        if os.path.exists(path) or slug in taken_uids:
            return JSONResponse(
                status_code=409,
                content={"ok": False, "error": f"{filename} already exists."},
            )

        cc = _build_character_config(
            conf_name=conf_name,
            conf_uid=slug,
            persona_prompt=str(persona),
            live2d_model_name=skin,
            voice=voice,
            character_name=fields["character_name"],
            avatar=fields["avatar"] or None,
            reply_language=fields["reply_language"] or None,
            voice_lang=fields["voice_lang"] or None,
            tts_model=fields["tts_model"] or None,
            ref_audio_path=fields["ref_audio_path"] or None,
            prompt_text=fields["prompt_text"] or None,
            prompt_lang=fields["prompt_lang"] or None,
        )
        try:
            await asyncio.to_thread(_write_character_yaml, path, cc)
        except Exception as e:
            logger.error(f"character write failed (slug={slug}): {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not write character file."},
            )

        logger.info(f"character created: slug={slug} file={filename}")
        return JSONResponse(
            {
                "ok": True,
                "filename": filename,
                "conf_uid": slug,
                "conf_name": conf_name,
                "restart_required": False,
            }
        )

    # ------------------------------------------------------------------ #
    @router.post("/api/character/avatar")
    async def upload_avatar(request: Request):
        """存下角色的頭像，回傳檔名。

        兩種送法都收：JSON 帶 data URL，或 multipart 帶檔案欄位。

        **存在伺服器端是刻意的。** 對話紀錄是從後端載入的，所以角色頭像也必須活在
        後端——不能像使用者自己的頭像那樣只存在瀏覽器的 localStorage 裡，否則換一台
        裝置看舊對話，AI 的臉會不見。

        回傳的檔名由呼叫端寫進角色的 avatar 欄位，畫面再從 /avatars/<檔名> 取用。
        """
        if not _is_local_request(request):
            return _forbidden()

        raw: Optional[bytes] = None
        ext: Optional[str] = None
        conf_uid: Optional[str] = None

        content_type = (request.headers.get("content-type") or "").lower()
        if content_type.startswith("multipart/form-data"):
            try:
                form = await request.form()
            except Exception:
                return _bad_request("Invalid multipart body.")
            upload = form.get("file")
            conf_uid = (
                form.get("conf_uid") if isinstance(form.get("conf_uid"), str) else None
            )
            if upload is None or not hasattr(upload, "read"):
                return _bad_request("Missing 'file' field.")
            # 副檔名取自上傳的檔名，但一定要在允許清單裡才收。
            up_name = getattr(upload, "filename", "") or ""
            up_ext = os.path.splitext(up_name)[1].lower()
            if up_ext not in AVATAR_ALLOWED_EXTS:
                return _bad_request("Unsupported image type.")
            ext = up_ext
            try:
                raw = await upload.read()
            except Exception:
                return _bad_request("Could not read the uploaded file.")
            if not raw or len(raw) > AVATAR_MAX_BYTES:
                return _bad_request("Image is empty or too large (max 4 MB).")
        else:
            try:
                body = await request.json()
            except Exception:
                return _bad_request("Invalid JSON body.")
            if not isinstance(body, dict):
                return _bad_request("Invalid JSON body.")
            conf_uid = (
                body.get("conf_uid") if isinstance(body.get("conf_uid"), str) else None
            )
            decoded = _decode_data_url(body.get("data") or "")
            if decoded is None:
                return _bad_request(
                    "Invalid image data (expect a data:image/...;base64 URL "
                    "under 4 MB)."
                )
            raw, ext = decoded

        filename = _safe_avatar_filename(conf_uid, ext)
        # _safe_avatar_filename never produces separators, but double-check the
        # final name can't escape AVATARS_DIR.
        if os.path.basename(filename) != filename:
            return _bad_request("Could not derive a safe filename.")
        try:
            await asyncio.to_thread(_write_avatar_atomic, filename, raw)
        except Exception as e:
            logger.error(f"avatar write failed: {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not save the avatar."},
            )

        logger.info(f"avatar uploaded: {filename} ({len(raw)} bytes)")
        return JSONResponse({"ok": True, "filename": filename})

    # ------------------------------------------------------------------ #
    @router.post("/api/background")
    async def upload_background(request: Request):
        """存下背景圖，回傳檔名。

        同樣存在伺服器端，理由跟頭像一樣：換裝置也看得到。這也是為什麼背景選單
        可以直接提供上傳，而不必叫使用者自己把檔案丟進資料夾。

        存好之後 scan_bg_directory 就掃得到，會自動出現在選單裡。
        """
        if not _is_local_request(request):
            return _forbidden()

        content_type = (request.headers.get("content-type") or "").lower()
        if not content_type.startswith("multipart/form-data"):
            return _bad_request("Expected a multipart/form-data upload.")
        try:
            form = await request.form()
        except Exception:
            return _bad_request("Invalid multipart body.")
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            return _bad_request("Missing 'file' field.")
        up_name = getattr(upload, "filename", "") or ""
        up_ext = os.path.splitext(up_name)[1].lower()
        if up_ext not in BG_ALLOWED_EXTS:
            return _bad_request("Unsupported image type (use JPG, PNG, or GIF).")
        try:
            raw = await upload.read()
        except Exception:
            return _bad_request("Could not read the uploaded file.")
        if not raw or len(raw) > BG_MAX_BYTES:
            return _bad_request("Image is empty or too large (max 12 MB).")

        filename = _safe_bg_filename(up_name, up_ext)
        if os.path.basename(filename) != filename:
            return _bad_request("Could not derive a safe filename.")
        try:
            await asyncio.to_thread(_write_bg_atomic, filename, raw)
        except Exception as e:
            logger.error(f"background write failed: {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not save the background."},
            )
        logger.info(f"background uploaded: {filename} ({len(raw)} bytes)")
        return JSONResponse({"ok": True, "filename": filename})

    # ------------------------------------------------------------------ #
    @router.put("/api/characters/{filename}")
    async def update_character(filename: str, request: Request):
        if not _is_local_request(request):
            return _forbidden()
        # ---- Base character (conf.yaml): surgical ruamel round-trip edit. ----
        if filename == CONF_PATH:
            if not os.path.exists(CONF_PATH):
                return JSONResponse(
                    status_code=404,
                    content={"ok": False, "error": "Base character not found."},
                )
            try:
                body = await request.json()
            except Exception:
                return _bad_request("Invalid JSON body.")
            if not isinstance(body, dict):
                return _bad_request("Invalid JSON body.")

            try:
                existing = read_yaml(CONF_PATH) or {}
            except Exception:
                return JSONResponse(
                    status_code=500,
                    content={"ok": False, "error": "Existing file is unreadable."},
                )
            existing_cc = existing.get("character_config", {}) or {}

            fields = _extract_body_fields(body)
            conf_name = fields["conf_name"]
            persona = fields["persona_prompt"]
            skin = fields["live2d_model_name"]
            voice = fields["voice"] or None

            if not conf_name:
                return _bad_request("Missing display name (conf_name).")
            if not persona or not str(persona).strip():
                return _bad_request("Missing persona_prompt.")
            if not skin:
                return _bad_request("Missing live2d_model_name (skin).")

            try:
                await asyncio.to_thread(_rescan_skins)
            except Exception as e:
                logger.warning(f"pre-update skin scan failed: {type(e).__name__}")
            registered = {m.get("name") for m in _load_model_dict()}
            if skin not in registered:
                return _bad_request(f"Skin '{skin}' is not a registered Live2D model.")

            try:
                await asyncio.to_thread(
                    _update_base_character_config,
                    conf_name=conf_name,
                    persona_prompt=str(persona),
                    live2d_model_name=skin,
                    voice=voice,  # None -> leave existing voice untouched
                    character_name=fields["character_name"]
                    if fields["character_name"] is not None
                    else existing_cc.get("character_name"),
                    # Avatar: explicit "" clears; absent key (None) preserves on disk.
                    avatar=fields["avatar"] if fields["avatar"] is not None else None,
                    # None（缺鍵）＝維持原狀；""＝清掉改回沿用全域。
                    reply_language=fields["reply_language"],
                    voice_lang=fields["voice_lang"],
                    tts_model=fields["tts_model"],
                    ref_audio_path=fields["ref_audio_path"],
                    prompt_text=fields["prompt_text"],
                    prompt_lang=fields["prompt_lang"],
                )
            except Exception as e:
                logger.error(f"base character update failed: {type(e).__name__}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"ok": False, "error": "Could not write base character."},
                )

            logger.info("base character (conf.yaml) updated")
            return JSONResponse(
                {
                    "ok": True,
                    "filename": CONF_PATH,
                    "conf_uid": existing_cc.get("conf_uid"),
                    "conf_name": conf_name,
                    # Editing the active character only applies after re-select.
                    "restart_required": False,
                }
            )

        path = _safe_character_path(filename)
        if path is None:
            return _bad_request("Invalid character filename.")
        if not os.path.exists(path):
            return JSONResponse(
                status_code=404, content={"ok": False, "error": "Character not found."}
            )

        try:
            body = await request.json()
        except Exception:
            return _bad_request("Invalid JSON body.")
        if not isinstance(body, dict):
            return _bad_request("Invalid JSON body.")

        # conf_uid / slug / filename are IMMUTABLE — keep the existing conf_uid so
        # we never orphan chat_history/<conf_uid>/<history_uid>/core_memory.md.
        try:
            existing = read_yaml(path) or {}
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Existing file is unreadable."},
            )
        existing_cc = existing.get("character_config", {}) or {}
        conf_uid = existing_cc.get("conf_uid") or filename[:-5]

        fields = _extract_body_fields(body)
        conf_name = fields["conf_name"]
        persona = fields["persona_prompt"]
        skin = fields["live2d_model_name"]
        voice = fields["voice"] or None

        if not conf_name:
            return _bad_request("Missing display name (conf_name).")
        if not persona or not str(persona).strip():
            return _bad_request("Missing persona_prompt.")
        if not skin:
            return _bad_request("Missing live2d_model_name (skin).")

        try:
            await asyncio.to_thread(_rescan_skins)
        except Exception as e:
            logger.warning(f"pre-update skin scan failed: {type(e).__name__}")
        registered = {m.get("name") for m in _load_model_dict()}
        if skin not in registered:
            return _bad_request(f"Skin '{skin}' is not a registered Live2D model.")

        cc = _build_character_config(
            conf_name=conf_name,
            conf_uid=conf_uid,  # immutable
            persona_prompt=str(persona),
            live2d_model_name=skin,
            voice=voice,  # None -> tts_config omitted -> re-inherits base voice
            character_name=fields["character_name"]
            if fields["character_name"] is not None
            else existing_cc.get("character_name"),
            # 頭像：明確給空字串＝清掉（改回沿用底稿或顯示名字首字）；
            # an absent key (None) preserves whatever was on disk.
            avatar=fields["avatar"]
            if fields["avatar"] is not None
            else existing_cc.get("avatar"),
            # 覆寫檔是整份重寫的，所以「這次沒帶」要退回磁碟上的現值，否則
            # 每次編輯別的欄位都會把語言設定清掉。
            reply_language=(
                fields["reply_language"]
                if fields["reply_language"] is not None
                else existing_cc.get("reply_language")
            ),
            voice_lang=(
                fields["voice_lang"]
                if fields["voice_lang"] is not None
                else (existing_cc.get("tts_config", {}) or {})
                .get("gpt_sovits_tts", {})
                .get("text_lang")
            ),
            # 這一格就是「一直被切回去」的現場：覆寫檔每次都整份重寫，這次沒帶
            # tts_model 就必須退回磁碟上的現值。少了這個 fallback，使用者改個
            # 頭像或人設，角色釘的引擎就被清掉，聲音悄悄換人。
            tts_model=(
                fields["tts_model"]
                if fields["tts_model"] is not None
                else (existing_cc.get("tts_config", {}) or {}).get("tts_model")
            ),
            # 跟 voice_lang 同一個理由：覆寫檔是整份重寫的，這次沒帶就必須退回
            # 磁碟現值，否則改個頭像就把手寫的聲線設定清掉——芙莉蓮與表情測試
            # 那兩份完整的 gpt_sovits_tts 區塊就是這樣被洗掉的。
            ref_audio_path=(
                fields["ref_audio_path"]
                if fields["ref_audio_path"] is not None
                else (existing_cc.get("tts_config", {}) or {})
                .get("gpt_sovits_tts", {})
                .get("ref_audio_path")
            ),
            prompt_text=(
                fields["prompt_text"]
                if fields["prompt_text"] is not None
                else (existing_cc.get("tts_config", {}) or {})
                .get("gpt_sovits_tts", {})
                .get("prompt_text")
            ),
            prompt_lang=(
                fields["prompt_lang"]
                if fields["prompt_lang"] is not None
                else (existing_cc.get("tts_config", {}) or {})
                .get("gpt_sovits_tts", {})
                .get("prompt_lang")
            ),
        )
        try:
            await asyncio.to_thread(_write_character_yaml, path, cc)
        except Exception as e:
            logger.error(f"character update failed ({filename}): {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not write character file."},
            )

        logger.info(f"character updated: file={filename} conf_uid={conf_uid}")
        return JSONResponse(
            {
                "ok": True,
                "filename": filename,
                "conf_uid": conf_uid,
                "conf_name": conf_name,
                # 編輯的如果正好是當前角色，要重新選一次才會套用。
                "restart_required": False,
            }
        )

    # ------------------------------------------------------------------ #
    @router.delete("/api/characters/{filename}")
    async def delete_character(filename: str, request: Request):
        if not _is_local_request(request):
            return _forbidden()
        if filename == CONF_PATH:
            return _bad_request("Cannot delete the base character (conf.yaml).")
        path = _safe_character_path(filename)
        if path is None:
            return _bad_request("Invalid character filename.")
        if not os.path.exists(path):
            return JSONResponse(
                status_code=404, content={"ok": False, "error": "Character not found."}
            )

        try:
            # 優先丟進垃圾桶（救得回來），不支援才真的刪。
            try:
                from send2trash import send2trash

                send2trash(path)
            except Exception:
                os.remove(path)
        except Exception as e:
            logger.error(f"character delete failed ({filename}): {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not delete character file."},
            )

        # **刻意不刪對話紀錄與記憶**：使用者刪的是角色設定，不是那段關係。
        logger.info(f"character deleted: file={filename}")
        return JSONResponse({"ok": True, "filename": filename})

    return router
