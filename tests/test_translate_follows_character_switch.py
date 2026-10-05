"""換角色時，翻譯器要讀「這次載入的角色」的口頭禪與專有名詞。

load_from_config 在最後才把 self.character_config 換成新角色，init_translate
卻在那之前被呼叫。翻譯器若讀 self.character_config，拿到的會是上一個角色的
名單；兩個角色共用同一份翻譯設定和同一種語音語言時，舊引擎甚至不會重建。

這裡走真實的 load_from_config（只把跟翻譯無關的引擎換成空殼），A → B → A
各換一次，每一次的翻譯器都只能帶著當下那個角色自己的名單。
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber import persona_store
from src.open_llm_vtuber.service_context import ServiceContext

# 兩個角色共用同一份翻譯設定物件：config_changed 永遠是 False，
# 語音語言也一樣，所以只剩名單本身能觸發重建。
TRANSLATOR_CONFIG = SimpleNamespace(
    translate_audio=True,
    translate_subtitle=True,
    translate_provider="llm",
    llm=SimpleNamespace(
        model_dump=lambda: {
            "api_endpoint": "http://translator.test/v1/chat/completions",
            "model": "local-model",
            "target_lang": "日文",
        }
    ),
)


def _config(conf_uid, catchphrases, protected_names):
    character = SimpleNamespace(
        conf_uid=conf_uid,
        persona_prompt=f"I am {conf_uid}.",
        live2d_model_name="model",
        asr_config=None,
        tts_config=SimpleNamespace(
            tts_model="edge_tts",
            edge_tts=SimpleNamespace(voice="ja-JP-NanamiNeural"),
        ),
        vad_config=None,
        agent_config=SimpleNamespace(
            agent_settings=SimpleNamespace(
                conversation=SimpleNamespace(use_mcpp=False, mcp_enabled_servers=[])
            )
        ),
        tts_preprocessor_config=SimpleNamespace(translator_config=TRANSLATOR_CONFIG),
        reply_language="Traditional Chinese (Taiwan)",
        catchphrases=catchphrases,
        protected_names=protected_names,
    )
    return SimpleNamespace(
        character_config=character,
        system_config=SimpleNamespace(player_language="zh-TW"),
    )


CHARACTER_A = _config("alpha", {"nya": "にゃ"}, {"星見": ["星美"]})
CHARACTER_B = _config("beta", {"desu": "です"}, {"月詠": ["月影"]})


def _context(monkeypatch):
    monkeypatch.setattr(persona_store, "get_active_persona_id", lambda uid: None)

    async def _noop_async(*args, **kwargs):
        return None

    context = ServiceContext()
    context.init_live2d = lambda *a, **k: None
    context.init_asr = lambda *a, **k: None
    context.init_tts = lambda *a, **k: None
    context.init_vad = lambda *a, **k: None
    context._init_mcp_components = _noop_async
    context.init_agent = _noop_async
    return context


def _assert_translators_belong_to(context, mine, other):
    audio_prompt = context.translate_engine._system_prompt()
    for source, target in mine.character_config.catchphrases.items():
        assert f"{source} → {target}" in audio_prompt
    for source in other.character_config.catchphrases:
        assert source not in audio_prompt

    # 字幕翻譯器帶的是同一份口頭禪，但原樣保留：來源寫法 → 來源寫法。
    subtitle = context.subtitle_translate_engine
    assert subtitle.catchphrases == {
        source: source for source in mine.character_config.catchphrases
    }
    subtitle_prompt = subtitle._system_prompt()
    for source, target in mine.character_config.catchphrases.items():
        assert source in subtitle_prompt
        assert target not in subtitle_prompt
    for source in other.character_config.catchphrases:
        assert source not in subtitle_prompt

    for engine in (context.translate_engine, context.subtitle_translate_engine):
        assert engine.protected_names == mine.character_config.protected_names


def test_each_switch_rebuilds_translators_for_the_incoming_character(monkeypatch):
    context = _context(monkeypatch)

    for mine, other in (
        (CHARACTER_A, CHARACTER_B),
        (CHARACTER_B, CHARACTER_A),
        (CHARACTER_A, CHARACTER_B),
    ):
        asyncio.run(context.load_from_config(mine))

        _assert_translators_belong_to(context, mine, other)


def test_the_subtitle_translator_keeps_catchphrases_unchanged(monkeypatch):
    """口頭禪的目標寫法是為語音語言寫的；字幕不換寫法，原樣保留來源寫法。

    實際發生過：字幕翻譯器把「konpeko！」翻成「孔佩可！」。
    """
    context = _context(monkeypatch)

    asyncio.run(context.load_from_config(CHARACTER_A))

    assert context.subtitle_translate_engine.catchphrases == {"nya": "nya"}
    prompt = context.subtitle_translate_engine._system_prompt()
    assert "nya" in prompt
    assert "にゃ" not in prompt
    assert "→" not in prompt
    # 音訊翻譯器照舊帶真正的對照表。
    assert context.translate_engine.catchphrases == {"nya": "にゃ"}
