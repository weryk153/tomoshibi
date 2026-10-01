"""工廠測試共用的參數。不匯入引擎。"""

from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig


class FakeLive2D:
    @staticmethod
    def extract_emotion(_text):
        return None

    @staticmethod
    def extract_emotion_keys(_text):
        return []

    @staticmethod
    def extract_motions(_text):
        return None


def factory_arguments(choice="character_engine_agent"):
    return {
        "conversation_agent_choice": choice,
        "agent_settings": {
            "conversation": {"llm_provider": "lmstudio_llm", "use_mcpp": False},
            "character_engine_agent": {},
        },
        "llm_configs": {
            "lmstudio_llm": {
                "base_url": "http://127.0.0.1:1/v1",
                "model": "stub",
                "llm_api_key": "not-needed",
                "temperature": 0.7,
                "extra_body": {"reasoning_effort": "none", "presence_penalty": 0.6},
            }
        },
        "system_prompt": "你是紅莉栖。",
        "live2d_model": FakeLive2D(),
        "tts_preprocessor_config": TTSPreprocessorConfig(
            remove_special_char=True,
            translator_config={
                "translate_audio": False,
                "translate_provider": "deeplx",
            },
        ),
        "conf_uid": "kurisu",
        "character_name": "紅莉栖",
    }
