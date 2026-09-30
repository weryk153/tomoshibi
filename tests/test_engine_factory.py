"""選了 character_engine_agent 時，工廠建得出一個由引擎驅動的 agent。

引擎那一側（CharacterCompanion）每個角色同一時間只有一個，所有 agent 共用；
agent 卻是每次儲存設定就重建一個。
"""

import asyncio

import pytest

from src.open_llm_vtuber.agent.agent_factory import AgentFactory
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource


from tests.engine_factory_arguments import factory_arguments  # noqa: E402

pytest.importorskip("ai_character_engine")

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
    talking, thinking = Offline.built

    assert talking.request_options == {
        "temperature": 0.7,
        "extra_body": {"reasoning_effort": "none", "presence_penalty": 0.6},
    }
    assert thinking.request_options["temperature"] == pytest.approx(0.1)
    assert thinking.request_options["extra_body"] == {"reasoning_effort": "none"}
    assert {client.options["model"] for client in Offline.built} == {"stub"}


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
    """basic_memory_agent 留 20000 字、至少 24 則。引擎預設 40 則，語音對話一句
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
    arguments["agent_settings"]["basic_memory_agent"]["llm_provider"] = "claude_llm"
    arguments["llm_configs"]["claude_llm"] = {"model": "claude", "base_url": "x"}

    with pytest.raises(ValueError) as caught:
        AgentFactory.create_agent(**arguments)

    assert "basic_memory_agent" in str(caught.value)
