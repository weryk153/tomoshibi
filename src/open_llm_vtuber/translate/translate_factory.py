from .deeplx import DeepLXTranslate
from .tencent import TencentTranslate
from .llm_translate import LLMTranslate
from .translate_interface import TranslateInterface


class TranslateFactory:
    @staticmethod
    def get_translator(
        translate_provider: str, translate_provider_config: dict
    ) -> TranslateInterface:
        translate_provider = translate_provider.lower()
        if translate_provider == "deeplx":
            return DeepLXTranslate(
                api_endpoint=translate_provider_config.get("deeplx_api_endpoint"),
                target_lang=translate_provider_config.get("deeplx_target_lang"),
            )
        elif translate_provider == "tencent":
            return TencentTranslate(
                secret_id=translate_provider_config.get("secret_id"),
                secret_key=translate_provider_config.get("secret_key"),
                region=translate_provider_config.get("region"),
                source_lang=translate_provider_config.get("source_lang"),
                target_lang=translate_provider_config.get("target_lang"),
            )
        elif translate_provider == "llm":
            return LLMTranslate(
                api_endpoint=translate_provider_config.get("api_endpoint"),
                model=translate_provider_config.get("model"),
                target_lang=translate_provider_config.get("target_lang"),
                # 沒帶這兩個的話，推理模型會撞預設的 30 秒逾時、或把答案放進
                # reasoning_content 而 content 留空，兩者都靜默 fallback 回原文。
                extra_body=translate_provider_config.get("extra_body"),
                timeout=translate_provider_config.get("timeout") or 30,
            )
        else:
            raise ValueError(f"Unsupported translate provider: {translate_provider}")
