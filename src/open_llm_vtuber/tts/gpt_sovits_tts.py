####
# change from xTTS.py
####

import os
import re

import requests
from loguru import logger
from .tts_interface import TTSInterface


class TTSEngine(TTSInterface):
    """GPT-SoVITS，可依情緒切換參考音。

    參考音決定語氣。原本整支只有一個寫死的 ref_audio_path，所以不管她臉上是什麼
    表情，聲音永遠是同一個語氣——臉在笑，聲音是平的。

    emotion_refs 把「情緒關鍵字 → 參考音」對起來。關鍵字用的就是 Live2D 模型
    emotionMap 裡的那些名字（LLM 每輪寫在回覆開頭的那個），所以表情跟語氣自然
    對得上，不需要第二套詞彙。

    參考音跟它的逐字稿是一組的：GPT-SoVITS 要 prompt_text 才能對齊音色，給錯
    的逐字稿輸出會歪掉。所以對照表的每一項都是 {ref_audio_path, prompt_text}，
    prompt_lang 沒寫就沿用預設。

    對不上、檔案不存在、或整個沒設定，一律退回預設參考音——語氣不對總比沒有
    聲音好。
    """

    supports_emotion = True

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:9880/tts",
        text_lang: str = "zh",
        ref_audio_path: str = "",
        prompt_lang: str = "zh",
        prompt_text: str = "",
        text_split_method: str = "cut5",
        batch_size: str = "1",
        media_type: str = "wav",
        streaming_mode: str = "ture",
        emotion_refs: dict | None = None,
    ):
        self.api_url = api_url
        self.text_lang = text_lang
        self.ref_audio_path = ref_audio_path
        self.prompt_lang = prompt_lang
        self.prompt_text = prompt_text
        self.text_split_method = text_split_method
        self.batch_size = batch_size
        self.media_type = media_type
        self.streaming_mode = streaming_mode
        self.emotion_refs = self._normalize_emotion_refs(emotion_refs)

    @staticmethod
    def _normalize_emotion_refs(raw) -> dict:
        """設定是使用者手打的，什麼都可能出現；壞掉的項目丟掉而不是讓 TTS 爆掉。

        少了 ref_audio_path 或 prompt_text 的項目直接不收——半套的設定會讓
        GPT-SoVITS 拿錯的逐字稿去對齊，輸出比退回預設更糟。
        """
        if not isinstance(raw, dict):
            return {}
        refs = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            path = str(value.get("ref_audio_path") or "").strip()
            prompt = str(value.get("prompt_text") or "").strip()
            if not path or not prompt:
                logger.warning(
                    f"[tts] emotion_refs['{key}'] 缺 ref_audio_path 或 prompt_text，略過"
                )
                continue
            refs[str(key).strip().lower()] = {
                "ref_audio_path": path,
                "prompt_text": prompt,
                "prompt_lang": str(value.get("prompt_lang") or "").strip(),
            }
        return refs

    def _ref_for(self, emotion) -> tuple:
        """回傳這個情緒該用的 (ref_audio_path, prompt_text, prompt_lang)。

        任何對不上的情況都退回預設，而且只記 debug——LLM 寫出來的關鍵字有沒有
        對應的參考音，是使用者錄了沒有的問題，不是錯誤。
        """
        if not emotion or not self.emotion_refs:
            return self.ref_audio_path, self.prompt_text, self.prompt_lang
        ref = self.emotion_refs.get(str(emotion).strip().lower())
        if not ref:
            logger.debug(f"[tts] 情緒 '{emotion}' 沒有對應的參考音，用預設")
            return self.ref_audio_path, self.prompt_text, self.prompt_lang
        if not os.path.isfile(ref["ref_audio_path"]):
            logger.warning(
                f"[tts] emotion_refs['{emotion}'] 的參考音不存在："
                f"{ref['ref_audio_path']}，用預設"
            )
            return self.ref_audio_path, self.prompt_text, self.prompt_lang
        return (
            ref["ref_audio_path"],
            ref["prompt_text"],
            ref["prompt_lang"] or self.prompt_lang,
        )

    def generate_audio(self, text, file_name_no_ext=None, emotion=None):
        file_name = self.generate_cache_file_name(file_name_no_ext, self.media_type)
        cleaned_text = re.sub(r"\[.*?\]", "", text)
        cleaned_text = re.sub(r"\(\*[^)]*\)", "", cleaned_text)  # strip (*action*) roleplay text
        cleaned_text = re.sub(r"\*[^*]+\*", "", cleaned_text)  # strip *action* inline text
        cleaned_text = cleaned_text.strip()
        ref_audio_path, prompt_text, prompt_lang = self._ref_for(emotion)
        # Prepare the data for the POST request
        data = {
            "text": cleaned_text,
            "text_lang": self.text_lang,
            "ref_audio_path": ref_audio_path,
            "prompt_lang": prompt_lang,
            "prompt_text": prompt_text,
            "text_split_method": self.text_split_method,
            "batch_size": self.batch_size,
            "media_type": self.media_type,
            "streaming_mode": self.streaming_mode,
        }

        # Send POST request to the TTS API
        response = requests.get(self.api_url, params=data, timeout=120)

        # Check if the request was successful
        if response.status_code == 200:
            # Save the audio content to a file
            with open(file_name, "wb") as audio_file:
                audio_file.write(response.content)
            logger.info(f"TTS audio saved: {file_name} ({len(response.content)} bytes)")
            return file_name
        else:
            # Handle errors or unsuccessful requests
            logger.critical(
                f"Error: Failed to generate audio. Status code: {response.status_code}"
            )
            return None
