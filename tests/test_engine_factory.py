"""選了 character_engine_agent 時，工廠建得出一個由引擎驅動的 agent。

引擎那一側（CharacterCompanion）每個角色同一時間只有一個，所有 agent 共用；
agent 卻是每次儲存設定就重建一個。
"""

import asyncio
import inspect

import pytest

from src.open_llm_vtuber.agent.agent_factory import AgentFactory
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource


from tests.engine_factory_arguments import factory_arguments  # noqa: E402

pytest.importorskip("ai_character_engine")

from ai_character_engine.companion import CharacterCompanion  # noqa: E402
from ai_character_engine.llm.models import LLMResponse, LLMStreamChunk  # noqa: E402

from src.open_llm_vtuber.character_engine import factory  # noqa: E402


class Offline:
    """頂替引擎的模型 client，記下它是用什麼設定建的。"""

    built = []

    def __init__(self, **options):
        self.options = options
        self.request_options = options.get("request_options", {})
        Offline.built.append(self)

    async def generate(self, messages, *, tools=None):
        return LLMResponse(text="{}", model="offline")

    async def stream_generate(self, messages, *, tools=None):
        yield LLMStreamChunk(text="嗯。")
        yield LLMStreamChunk(
            final=True, response=LLMResponse(text="嗯。", model="offline")
        )


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(factory, "_LIVE", {})
    monkeypatch.setattr(factory, "_MOOD_LISTENERS", {})
    monkeypatch.setattr(factory, "_engine_client", lambda **options: Offline(**options))
    monkeypatch.setattr(factory, "detect_context_window", lambda *a, **k: None)
    Offline.built = []


async def say(agent, text):
    batch = BatchInput(texts=[TextData(source=TextSource.INPUT, content=text)])
    return [output async for output in agent.chat(batch)]


def test_her_state_lives_next_to_that_characters_chat_history(tmp_path):
    async def scenario():
        created = AgentFactory.create_agent(**factory_arguments())
        await say(created, "你好")
        await created.close()

    asyncio.run(scenario())

    assert (tmp_path / "chat_history" / "kurisu" / "engine" / "state.json").is_file()


def test_the_folder_name_is_cleaned_like_the_chat_historys(tmp_path):
    arguments = factory_arguments()
    arguments["conf_uid"] = "../../outside"

    async def scenario():
        created = AgentFactory.create_agent(**arguments)
        await say(created, "你好")
        await created.close()

    asyncio.run(scenario())

    assert (tmp_path / "chat_history" / "outside" / "engine" / "state.json").is_file()
    assert not (tmp_path.parent / "outside").exists()


def test_a_conf_uid_that_is_not_a_name_is_refused(tmp_path):
    arguments = factory_arguments()
    arguments["conf_uid"] = ".."

    with pytest.raises(ValueError):
        AgentFactory.create_agent(**arguments)

    assert not (tmp_path / "chat_history").exists()


def test_she_is_the_persona_the_host_composed():
    created = AgentFactory.create_agent(**factory_arguments())
    character = created._companion().character

    assert (character.id, character.name) == ("kurisu", "紅莉栖")
    assert character.description.startswith("你是紅莉栖。")


def test_rebuilding_the_agent_keeps_the_same_engine_side():
    """每次儲存設定都會重建 agent；各建各的話，它們會寫同一個資料夾。"""

    async def scenario():
        first = AgentFactory.create_agent(**factory_arguments())
        await say(first, "一")
        second = AgentFactory.create_agent(**factory_arguments())
        await say(second, "二")
        return first._companion(), second._companion()

    one, two = asyncio.run(scenario())

    assert one is two
    assert two.snapshot().trust == pytest.approx(50.6)


def test_a_persona_edit_does_not_replace_the_engine_side():
    """人設與記憶每輪都可能刷新；那是改她的描述，不是換一個她。"""

    async def scenario():
        first = AgentFactory.create_agent(**factory_arguments())
        await say(first, "一")
        edited = factory_arguments()
        edited["system_prompt"] = "你是鋼琴家。"
        second = AgentFactory.create_agent(**edited)
        await say(second, "二")
        return first._companion(), second._companion()

    one, two = asyncio.run(scenario())

    assert one is two
    assert two.character.description.startswith("你是鋼琴家。")


def test_changing_the_model_moves_every_agent_to_a_new_engine_side():
    async def scenario():
        before = AgentFactory.create_agent(**factory_arguments())
        await say(before, "一")
        old = before._companion()
        changed = factory_arguments()
        changed["llm_configs"]["lmstudio_llm"]["model"] = "another-model"
        after = AgentFactory.create_agent(**changed)
        await say(before, "舊連線繼續聊")
        return before, after, old

    before, after, old = asyncio.run(scenario())

    assert before._companion() is after._companion()
    assert before._companion() is not old
    assert old.usable_in_running_loop() is False
    assert after._companion().snapshot().trust == pytest.approx(50.6)


def test_she_talks_with_the_hosts_settings_and_thinks_with_plain_ones():
    """背景工作要的是穩定的 JSON：溫度壓低，只留「關掉思考模式」這類欄位——
    presence_penalty 會懲罰 JSON 裡本來就該重複的鍵名。"""
    AgentFactory.create_agent(**factory_arguments())
    talking, thinking, _picking = Offline.built

    assert talking.request_options == {
        "temperature": 0.7,
        "extra_body": {"reasoning_effort": "none", "presence_penalty": 0.6},
    }
    assert thinking.request_options["temperature"] == pytest.approx(0.1)
    assert thinking.request_options["extra_body"] == {"reasoning_effort": "none"}
    assert {client.options["model"] for client in Offline.built} == {"stub"}


def test_her_background_work_can_run_on_another_model():
    """她講話用設定頁選的模型，背景工作（情緒、記憶、目標…）可以交給另一個端點，
    例如另一台電腦上的同一顆模型：她講話時就不用跟背景工作搶。"""
    arguments = factory_arguments()
    arguments["agent_settings"]["character_engine_agent"] = {
        "background_base_url": "http://127.0.0.1:1235/v1",
        "background_model": "qwen/qwen3.5-9b",
        "goal_every": 9,
    }

    agent = AgentFactory.create_agent(**arguments)
    talking, thinking, _picking = Offline.built

    assert talking.options["model"] == "stub"
    assert talking.options["base_url"] != "http://127.0.0.1:1235/v1"
    assert thinking.options["base_url"] == "http://127.0.0.1:1235/v1"
    assert thinking.options["model"] == "qwen/qwen3.5-9b"
    assert thinking.request_options["temperature"] == pytest.approx(0.1)
    assert agent._companion().settings.goal_every == 9


def test_her_faces_are_picked_with_a_short_answer_at_temperature_0():
    """每句的表情與動作（reply_actions）只要一行 JSON：溫度 0、最多 80 token，
    跟背景工作同一個端點；評測頁（scripts/eval_expression_pick.py）也是這組設定。"""
    arguments = factory_arguments()
    arguments["agent_settings"]["character_engine_agent"] = {
        "background_base_url": "http://127.0.0.1:1235/v1",
        "background_model": "qwen/qwen3.5-9b",
    }
    agent = AgentFactory.create_agent(**arguments)
    _talking, thinking, picking = Offline.built

    assert picking.request_options == {
        "temperature": 0,
        "max_tokens": 80,
        "extra_body": {"reasoning_effort": "none"},
    }
    assert picking.options["base_url"] == thinking.options["base_url"]
    assert picking.options["model"] == "qwen/qwen3.5-9b"
    if "actions_llm" in inspect.signature(CharacterCompanion).parameters:
        assert agent._companion()._actions_llm is picking


def test_on_lm_studio_her_picks_line_up_with_its_prompt_cache():
    """LM Studio 的提示快取 256 token 一格：挑表情的固定部分補到剛好跨過一格。"""
    agent = AgentFactory.create_agent(**factory_arguments())
    settings = agent._companion().settings
    if hasattr(settings, "actions_cache_block"):
        assert settings.actions_cache_block == 256


def test_other_servers_leave_the_picks_as_they_are():
    arguments = factory_arguments()
    arguments["agent_settings"]["conversation"]["llm_provider"] = "ollama_llm"
    arguments["llm_configs"] = {"ollama_llm": arguments["llm_configs"]["lmstudio_llm"]}
    settings = AgentFactory.create_agent(**arguments)._companion().settings
    assert getattr(settings, "actions_cache_block", 0) == 0


def test_half_a_background_endpoint_is_not_used():
    """只填了網址或只填了模型：用講話那一顆，不要拿半套設定去連。"""
    arguments = factory_arguments()
    arguments["agent_settings"]["character_engine_agent"] = {
        "background_base_url": "http://127.0.0.1:1235/v1",
        "background_model": "",
    }

    AgentFactory.create_agent(**arguments)
    talking, thinking, _picking = Offline.built

    assert thinking.options["base_url"] == talking.options["base_url"]
    assert thinking.options["model"] == talking.options["model"]


def test_changing_the_background_model_builds_a_new_engine_side():
    arguments = factory_arguments()
    first = AgentFactory.create_agent(**arguments)._companion()
    arguments = factory_arguments()
    arguments["agent_settings"]["character_engine_agent"] = {
        "background_base_url": "http://127.0.0.1:1235/v1",
        "background_model": "qwen/qwen3.5-9b",
    }
    second = AgentFactory.create_agent(**arguments)._companion()

    assert second is not first


def test_the_cognition_settings_reach_the_engine():
    arguments = factory_arguments()
    arguments["agent_settings"]["character_engine_agent"] = {
        "goal_every": 9,
        "timeout_seconds": 45.0,
        "max_rebase_turns": 5,
    }

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert (settings.goal_every, settings.call_timeout_seconds) == (9, 45.0)
    assert settings.max_turns_late == 5
    assert settings.emotion_every == 1


def test_her_mood_rhythm_from_the_config_file_reaches_the_engine():
    """走一遍真正的路：conf.yaml 的區塊先過 config_manager 的模型再 model_dump()
    交給工廠（service_context.init_agent 就是這樣做）。模型不認得的鍵在這一步就沒了。"""
    from src.open_llm_vtuber.config_manager.agent import AgentSettings

    arguments = factory_arguments()
    dumped = AgentSettings(
        conversation=arguments["agent_settings"]["conversation"],
        character_engine_agent={"mood_every": 5},
    ).model_dump()
    arguments["agent_settings"]["character_engine_agent"] = dumped[
        "character_engine_agent"
    ]

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert settings.mood_every == 5


def test_how_much_she_keeps_in_mind_reaches_the_engine():
    arguments = factory_arguments()
    arguments["agent_settings"]["character_engine_agent"] = {
        "goals_shown": 1,
        "thoughts_shown": 0,
    }

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert (settings.goals_shown, settings.thoughts_shown) == (1, 0)


def test_a_setting_the_installed_engine_does_not_have_is_left_out():
    """conf.yaml 可以比裝的引擎新（reply_check_every 是 1.2.0 才有的）：認不得的
    設定不傳，不能讓 CompanionSettings 丟 TypeError、她整個開不起來。"""
    arguments = factory_arguments()
    arguments["agent_settings"]["character_engine_agent"] = {
        "goal_every": 9,
        "an_engine_setting_from_the_future_every": 3,
    }

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert settings.goal_every == 9
    assert not hasattr(settings, "an_engine_setting_from_the_future_every")


def _engine_has(name):
    from dataclasses import fields

    from ai_character_engine.companion import CompanionSettings

    return name in {field.name for field in fields(CompanionSettings)}


@pytest.mark.skipif(
    not _engine_has("reply_check_every"), reason="installed engine predates 1.2.0"
)
def test_the_reply_check_rhythm_reaches_the_engine():
    from src.open_llm_vtuber.config_manager.agent import AgentSettings

    arguments = factory_arguments()
    dumped = AgentSettings(
        conversation=arguments["agent_settings"]["conversation"],
        character_engine_agent={"reply_check_every": 2},
    ).model_dump()
    arguments["agent_settings"]["character_engine_agent"] = dumped[
        "character_engine_agent"
    ]

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert settings.reply_check_every == 2


@pytest.mark.parametrize(
    "name, value",
    [
        ("user_state_every", 12),
        ("user_state_ttl_hours", 72.0),
        ("diary_every_hours", 0.0),
        ("diary_in_context", False),
        ("memory_conflicts", False),
    ],
)
def test_the_diary_user_state_and_conflict_settings_reach_the_engine(name, value):
    if not _engine_has(name):
        pytest.skip(f"installed engine has no {name}")
    from src.open_llm_vtuber.config_manager.agent import AgentSettings

    arguments = factory_arguments()
    dumped = AgentSettings(
        conversation=arguments["agent_settings"]["conversation"],
        character_engine_agent={name: value},
    ).model_dump()
    arguments["agent_settings"]["character_engine_agent"] = dumped[
        "character_engine_agent"
    ]

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert getattr(settings, name) == value


def test_the_newer_engine_settings_do_not_stop_an_older_engine():
    """conf 的預設帶著日記、使用者近況、記憶衝突；裝的引擎還沒有的話照樣開得起來。"""
    from src.open_llm_vtuber.config_manager.agent import AgentSettings

    arguments = factory_arguments()
    dumped = AgentSettings(
        conversation=arguments["agent_settings"]["conversation"],
        character_engine_agent={"goal_every": 9},
    ).model_dump()
    arguments["agent_settings"]["character_engine_agent"] = dumped[
        "character_engine_agent"
    ]

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert settings.goal_every == 9


def test_until_the_window_is_known_she_is_given_room_for_a_real_persona(monkeypatch):
    """實機：伺服器比模型早起來，問不到 window，引擎預設 8192 裝不下 Mao 的人設，
    主動發話那一輪直接失敗（Character context exceeds the configured context
    budget）。而且要等下一次儲存設定才會再問一次。"""
    monkeypatch.setattr(factory, "detect_context_window", lambda *a, **k: None)
    created = AgentFactory.create_agent(**factory_arguments())
    before = created._companion().runtime.context_builder.budget.context_window_tokens
    assert before >= 16384

    monkeypatch.setattr(factory, "detect_context_window", lambda *a, **k: 20992)

    # 每一輪都會來問「現在是哪一個」；模型載好之後不用重建 agent。
    after = created._companion().runtime.context_builder.budget.context_window_tokens
    assert after == 20992


def test_the_window_is_asked_for_a_few_times_not_on_every_turn_for_ever(monkeypatch):
    """雲端端點或 Ollama 永遠答不出 window。問一次是一次網路請求、在 event loop 上
    同步等，每輪都問等於每輪把所有連線的語音卡住一下。"""
    asked = []
    monkeypatch.setattr(
        factory, "detect_context_window", lambda *a, **k: asked.append(1) and None
    )
    created = AgentFactory.create_agent(**factory_arguments())
    for _ in range(20):
        created._companion()

    assert len(asked) <= factory.WINDOW_PROBES + 1


def test_a_turn_inside_the_cooldown_does_not_use_up_a_probe(monkeypatch):
    """問不到之後有一分鐘的冷卻，冷卻期內的呼叫沒有真的去問。LM Studio 是用到才
    載模型：建 companion 時第一次必然問不到，接下來一分鐘內連線、第一輪、第二輪
    各來問一次，額度就用光了，之後模型載好也永遠不會知道。"""
    from src.open_llm_vtuber import context_window

    now = [1000.0]
    loaded = [None]
    asked = []

    def probe(base_url, model):
        asked.append(1)
        return loaded[0]

    context_window.reset_cache()
    monkeypatch.setattr(context_window, "_probe_lmstudio", probe)
    monkeypatch.setattr(context_window.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        factory, "detect_context_window", context_window.detect_context_window
    )
    created = AgentFactory.create_agent(**factory_arguments())
    for _ in range(factory.WINDOW_PROBES + 2):
        created._companion()
    assert len(asked) == 1

    now[0] += 120.0
    loaded[0] = 8192
    companion = created._companion()

    assert len(asked) == 2
    assert companion.runtime.context_builder.budget.context_window_tokens == 8192
    context_window.reset_cache()


def test_a_window_that_is_detected_later_does_not_replace_her(monkeypatch):
    """模型還沒載入的時候問不到 window；晚一點問到了，是同一個她、換一個預算。"""
    first = AgentFactory.create_agent(**factory_arguments())._companion()
    monkeypatch.setattr(factory, "detect_context_window", lambda *a, **k: 20992)

    second = AgentFactory.create_agent(**factory_arguments())._companion()

    assert second is first
    assert second.runtime.context_builder.budget.context_window_tokens == 20992


def test_saving_settings_while_she_talks_lets_her_finish(monkeypatch):
    """設定一存，引擎那一側可能換一個。正在講的那句話要講完：主機那一輪沒有人
    取消它，中途斷掉的話前端等不到這一輪的結束訊號。"""
    gate = asyncio.Event()

    class Slow(Offline):
        async def stream_generate(self, messages, *, tools=None):
            yield LLMStreamChunk(text="嗯，")
            await gate.wait()
            yield LLMStreamChunk(text="我知道了。")
            yield LLMStreamChunk(
                final=True, response=LLMResponse(text="嗯，我知道了。", model="offline")
            )

    monkeypatch.setattr(factory, "_engine_client", lambda **options: Slow(**options))

    async def scenario():
        talking = AgentFactory.create_agent(**factory_arguments())
        turn = asyncio.ensure_future(say(talking, "你好"))
        for _ in range(20):
            await asyncio.sleep(0)
        changed = factory_arguments()
        changed["llm_configs"]["lmstudio_llm"]["model"] = "another-model"
        AgentFactory.create_agent(**changed)
        gate.set()
        return await turn

    outputs = asyncio.run(scenario())

    assert "".join(o.display_text.text for o in outputs) == "嗯，我知道了。"


def test_she_keeps_as_much_of_the_conversation_as_the_basic_agent():
    """引擎預設 40 則，語音對話一句
    很短，會比原本更早忘記前面講過的。"""
    default = AgentFactory.create_agent(**factory_arguments())._companion()
    assert default.settings.max_history_messages == 80

    arguments = factory_arguments()
    arguments["conf_uid"] = "another"
    arguments["agent_settings"]["character_engine_agent"] = {"max_history_messages": 30}
    assert (
        AgentFactory.create_agent(**arguments)
        ._companion()
        .settings.max_history_messages
        == 30
    )


def test_she_thinks_in_the_language_she_answers_in():
    """背景工作的指示是英文的，要模型自己從對話看出該用哪種語言。實機上一段
    中文對話的五筆記憶有四筆寫成英文。主機知道語言，就直接講。"""
    arguments = factory_arguments()
    arguments["output_language"] = "繁體中文"

    assert AgentFactory.create_agent(**arguments)._companion().settings.language == (
        "繁體中文"
    )


def test_the_detected_context_window_becomes_her_budget(monkeypatch):
    monkeypatch.setattr(factory, "detect_context_window", lambda *a, **k: 20992)

    companion = AgentFactory.create_agent(**factory_arguments())._companion()

    assert companion.runtime.context_builder.budget.context_window_tokens == 20992


def test_she_can_see_through_the_same_model_without_its_reasoning(monkeypatch):
    """本機模型預設會先思考再回答：描述一張圖要 23 秒；關掉是 3 秒。"""
    built = []
    monkeypatch.setattr(
        factory, "_engine_eyes", lambda **options: built.append(options) or "eyes"
    )

    companion = AgentFactory.create_agent(**factory_arguments())._companion()

    (options,) = built
    assert companion.sees
    assert (options["model"], options["base_url"]) == ("stub", "http://127.0.0.1:1/v1")
    assert options["request_options"]["extra_body"] == {"reasoning_effort": "none"}
    assert options["request_options"]["max_tokens"] <= 200


def test_a_provider_the_engine_cannot_talk_to_is_refused_with_the_way_out():
    arguments = factory_arguments()
    arguments["agent_settings"]["conversation"]["llm_provider"] = "claude_llm"
    arguments["llm_configs"]["claude_llm"] = {"model": "claude", "base_url": "x"}

    with pytest.raises(ValueError) as caught:
        AgentFactory.create_agent(**arguments)

    assert "OpenAI 相容" in str(caught.value)


def test_turning_long_term_memory_off_stops_the_engine_remembering_too():
    """記憶頁的開關說「關閉後她就不會再把新對話整理進記憶、也不會把舊記憶帶進
    對話」。接引擎時關掉它只停了主機自己那一份，引擎照樣抽記憶、照樣帶進對話。"""
    arguments = factory_arguments()
    arguments["long_term_memory_enabled"] = False

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert (settings.memory_every, settings.memories_recalled) == (0, 0)


def test_long_term_memory_on_leaves_the_engine_settings_alone():
    arguments = factory_arguments()
    arguments["long_term_memory_enabled"] = True
    arguments["agent_settings"]["character_engine_agent"] = {"memory_every": 3}

    settings = AgentFactory.create_agent(**arguments)._companion().settings

    assert settings.memory_every == 3
    assert settings.memories_recalled > 0


def test_an_engine_too_old_for_this_host_is_refused_with_the_way_out(monkeypatch):
    import ai_character_engine.companion as engine_companion

    monkeypatch.delattr(engine_companion, "SELF_MEMORY_LINE")

    with pytest.raises(RuntimeError, match="太舊"):
        factory.build_companion(
            conf_uid="kurisu",
            character_name="紅莉栖",
            system="你是紅莉栖。",
            provider="lmstudio_llm",
            llm_config={"base_url": "http://127.0.0.1:1234/v1", "model": "m"},
        )


# --- 她的心情 ---------------------------------------------------------------------


def test_her_mood_reaches_every_page_that_follows_that_character():
    async def scenario():
        created = AgentFactory.create_agent(**factory_arguments())
        heard, also = [], []
        stop = created.listen_to_mood(heard.append)
        created.listen_to_mood(also.append)
        companion = created._companion()
        companion.on_mood_change(companion.snapshot())
        stop()
        companion.on_mood_change(companion.snapshot())
        return heard, also

    heard, also = asyncio.run(scenario())

    assert [message["type"] for message in heard] == ["character-mood"]
    assert len(also) == 2


def test_a_rebuilt_engine_side_still_reaches_the_pages():
    """存設定換模型時引擎那一側會換一個；頁面不用重新連線也要收得到。"""

    async def scenario():
        before = AgentFactory.create_agent(**factory_arguments())
        heard = []
        before.listen_to_mood(heard.append)
        changed = factory_arguments()
        changed["llm_configs"]["lmstudio_llm"]["model"] = "another-model"
        after = AgentFactory.create_agent(**changed)
        companion = after._companion()
        companion.on_mood_change(companion.snapshot())
        return heard

    assert len(asyncio.run(scenario())) == 1


def test_a_listener_that_fails_does_not_keep_the_others_from_hearing():
    def broken(_message):
        raise RuntimeError("socket closed")

    async def scenario():
        created = AgentFactory.create_agent(**factory_arguments())
        heard = []
        created.listen_to_mood(broken)
        created.listen_to_mood(heard.append)
        companion = created._companion()
        companion.on_mood_change(companion.snapshot())
        return heard

    assert len(asyncio.run(scenario())) == 1


def test_an_engine_without_moods_is_refused_with_the_way_out(monkeypatch):
    import ai_character_engine.companion as engine_companion

    monkeypatch.delattr(engine_companion, "CHARACTER_MOODS")

    with pytest.raises(RuntimeError, match="太舊"):
        factory.build_companion(
            conf_uid="kurisu",
            character_name="紅莉栖",
            system="你是紅莉栖。",
            provider="lmstudio_llm",
            llm_config={"base_url": "http://127.0.0.1:1234/v1", "model": "m"},
        )


def test_her_background_persona_summary_does_not_change_her_conversation_prompt():
    """ContextBuilder 在 background（她的人設摘要）已經包含在 description 裡時省略
    Background 段落：接給心情背景工作讀人設，不會讓她自己的對話提示多一段。

    persona 只是系統提示裡的一段（前面有共用規則、後面有工具說明——跟
    construct_system_prompt 實際組出來的形狀一樣），不是整份系統提示本身；而且
    真的跑一輪，讓 _bring_up_to_date 那條每輪刷新 description／background 的路徑
    被走到，不是只看建構當下的那一次。"""
    from dataclasses import replace

    from ai_character_engine.context.builder import ContextBuilder

    persona_text = "你是紅莉栖，中二又傲嬌的天才駭客少女。"
    wrapped_system = (
        "Speak naturally and stay fully in character at all times.\n\n"
        f"{persona_text}\n\n"
        "## Tools\nYou may call a tool when it helps answer the user."
    )
    arguments = factory_arguments()
    arguments["system_prompt"] = wrapped_system
    arguments["persona_prompt"] = persona_text

    async def scenario():
        created = AgentFactory.create_agent(**arguments)
        await say(created, "你好")
        return created._companion().character

    character = asyncio.run(scenario())
    builder = ContextBuilder()

    assert character.background == persona_text
    assert character.background != character.description
    # agent 另外在系統提示後面加了記憶／打斷規則，description 不會一字不差等於
    # wrapped_system；但 persona 仍是它的一段，才是這個測試真正要的性質。
    assert character.description.startswith(wrapped_system)

    with_background = builder.build_system_prompt(character)
    without_background = builder.build_system_prompt(
        replace(character, background=None)
    )

    assert with_background == without_background
    assert "Background:" not in with_background
