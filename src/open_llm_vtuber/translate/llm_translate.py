from collections.abc import Mapping, Sequence

import httpx
import re
from loguru import logger

from ..conversation_quality import normalize_output_language_variant
from .translate_interface import TranslateInterface


class LLMTranslate(TranslateInterface):
    """用一般的 LLM 端點做翻譯，不必另外架翻譯服務。

    好處是玩家設好的模型就能直接拿來用，不用再裝一個 DeepLX；代價是慢——每一句
    都是一次完整的模型往返。要快就用 deeplx。
    """

    def __init__(
        self,
        api_endpoint: str,
        model: str,
        target_lang: str,
        extra_body: dict | None = None,
        timeout: int = 30,
        protected_names: "Mapping[str, Sequence[str]] | None" = None,
    ):
        self.api_endpoint = api_endpoint
        self.model = model
        self.target_lang = target_lang
        # Reasoning 模型預設會把答案放進 reasoning_content、content 留空，
        # 下面的空字串分支就會靜默 fallback 回原文——語音照念原文而畫面
        # 無錯誤。傳 {"reasoning_effort": "none"} 之類的值把推理關掉。
        self.extra_body = extra_body
        self.timeout = timeout
        # 這個角色的專有名詞：正式寫法 → 要折回去的錯誤寫法。由角色設定提供，
        # 這個模組不認得任何具體角色。見 CharacterConfig.protected_names。
        self.protected_names = dict(protected_names or {})

    @property
    def _is_traditional_chinese_target(self) -> bool:
        target = str(self.target_lang or "").strip().lower()
        return (
            target == "中文"
            or "繁體" in target
            or "繁体" in target
            or "taiwan" in target
            or "zh-tw" in target
            or "zh-hant" in target
        )

    def _system_prompt(self) -> str:
        variant_rule = ""
        if self._is_traditional_chinese_target:
            variant_rule = (
                " Use Traditional Chinese characters and natural Taiwan wording only; "
                "never output Simplified Chinese. The source is usually Japanese "
                "dialogue: interpret Japanese grammar before translating. In particular, "
                "無理をせず means 不要勉強自己 or 不要逞強, never 別扭地做. "
                "When Japanese omits a first-person subject, do not invent the plural "
                "pronoun 我們."
            )
            # 專有名詞是角色資料，不是翻譯引擎的知識。沒設就完全不提，避免
            # 對別人的角色下達莫名其妙的指令。
            if self.protected_names:
                spellings = "、".join(self.protected_names)
                variant_rule += (
                    " Treat character names as immutable proper nouns. These "
                    f"spellings must be reproduced exactly: {spellings}. Never "
                    "substitute a homophonic character."
                )
        return (
            f"You are a deterministic dialogue subtitle translator. Translate the "
            f"source into {self.target_lang}. Translate faithfully, sentence by "
            "sentence. Preserve every fact, subject, pronoun, name, number, negation, "
            "uncertainty, causal relationship, and logical relationship exactly. "
            "Never add, omit, explain, embellish, correct, or invert meaning. Keep the "
            "speaker in first person when the source is first person. Use natural spoken "
            f"wording in the target language.{variant_rule} Output only the translation "
            "itself, with no preface, commentary, romanization, or surrounding quotation "
            "marks. Preserve quotation marks that belong to quoted terms in the source."
        )

    def _request(self, text: str, retry: bool = False) -> str:
        if retry and self._is_traditional_chinese_target:
            # Qwen occasionally treats a very short Japanese fragment as a term to
            # preserve when given the long generic system contract (e.g. it returns
            # ``格好いいか？`` unchanged). A minimal Chinese repair request is much
            # more reliable for exactly this already-detected failure mode.
            messages = [
                {
                    "role": "user",
                    "content": (
                        "把下面的日文完整翻成臺灣繁體中文。不得保留任何"
                        "日文語法或假名；專有名詞後的日文助詞也必須翻譯，"
                        "例如「か」要依語意翻成「嗎」。不得改變主詞、否定或"
                        "原意；只輸出譯文。\n\n" + text
                    ),
                }
            ]
        else:
            user_text = text
            if retry:
                user_text = (
                    "The previous attempt left source-language text untranslated. "
                    "Translate every part of the source, while preserving its exact "
                    "meaning.\n\n" + text
                )
            messages = [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": user_text},
            ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "stream": False,
        }
        if self.extra_body:
            # OpenAI SDK's extra_body semantics merge values at the request root.
            payload.update(self.extra_body)
        resp = httpx.post(self.api_endpoint, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def translate(self, text: str) -> str:
        try:
            res = self._request(text)
            if not res:
                # empty translation (e.g. reasoning model returned nothing in
                # content): fall back to the original text, same as the except
                # branch, rather than passing an empty string downstream.
                logger.warning(
                    f"LLM translate returned empty for '{text}', using original"
                )
                return text

            # A Chinese subtitle containing kana still has an untranslated Japanese
            # fragment. Retry once with an explicit correction; this caught real output
            # such as "結論から言えば，絕對反對". One retry is bounded and
            # remains fail-soft if the local model cannot do better.
            if self._is_traditional_chinese_target and re.search(r"[぀-ヿ]", res):
                retry = self._request(text, retry=True)
                if retry:
                    res = retry

            if self._is_traditional_chinese_target:
                res = normalize_output_language_variant(
                    res, "Traditional Chinese (Taiwan)", self.protected_names
                )
                # Dialogue models occasionally pluralize an omitted Japanese subject
                # despite the contract above. Only correct the characteristic future
                # form and only for Japanese that has no explicit plural-first-person
                # marker; genuine 私たち/我々 remains untouched.
                if re.search(r"[぀-ヿ]", text) and not re.search(
                    r"(?:私たち|私達|僕たち|僕達|俺たち|俺達|我々|われわれ)",
                    text,
                ):
                    res = res.replace("我們將", "我會")
                # normalize_output_language_variant above already folded the
                # configured spellings back. Nothing character-specific belongs
                # here — the list comes from the character, via self.protected_names.
            logger.info(f"LLM translate: '{text}' -> '{res}'")
            return res
        except Exception as e:
            logger.critical(f"LLM translate error '{text}'. Error: {e}")
            # fallback: 回原文，避免對話中斷
            return text
