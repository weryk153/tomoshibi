"""Call-site tests for conversation_quality's wiring into BasicMemoryAgent.

The unit tests for build_turn_guidance() itself live in
tests/test_proactive_speech.py (a name that predates this module and was not
moved by this file's introduction). Everything here instead exercises the one
call site that makes the whole layering design real:
BasicMemoryAgent._to_messages() at
src/open_llm_vtuber/agent/agents/basic_memory_agent.py:336-343, which decides
what build_turn_guidance() actually receives for is_proactive.
Every existing test called build_turn_guidance() directly, so deleting either
keyword argument at that call site left all tests green despite breaking the
refactor's entire point.
"""

from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.agent.input_types import (
    BatchInput,
    TextData,
    TextSource,
)
from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig


class _FakeLLM:
    async def chat_completion(self, messages, system=None, tools=None):
        yield "placeholder"


class _FakeLive2D:
    @staticmethod
    def extract_emotion(_text):
        return None

    @staticmethod
    def extract_motions(_text):
        return None


def _tts_config() -> TTSPreprocessorConfig:
    return TTSPreprocessorConfig(
        remove_special_char=True,
        translator_config={
            "translate_audio": False,
            "translate_provider": "deeplx",
        },
    )


def _agent() -> BasicMemoryAgent:
    return BasicMemoryAgent(
        llm=_FakeLLM(),
        system="system",
        live2d_model=_FakeLive2D(),
        tts_preprocessor_config=_tts_config(),
    )


def _user_text(messages) -> str:
    return messages[-1]["content"][0]["text"]


def test_proactive_batch_suppresses_the_yes_no_user_intent_rule():
    """A synthetic proactive prompt is not something the user asked; the
    yes/no rule's substring match on 「有沒有」 must not fire on it."""
    agent = _agent()
    batch = BatchInput(
        texts=[
            TextData(
                source=TextSource.INPUT,
                content="自然地接續話題，確認背後有沒有什麼值得一提的細節。",
            )
        ],
        metadata={"proactive_speak": True, "skip_memory": True},
    )

    messages = agent._to_messages(batch)

    assert "不是答案" not in _user_text(messages)


def test_non_proactive_batch_with_the_same_text_gets_the_yes_no_rule():
    """Same text, proactive_speak absent: proves the previous test is not
    vacuous — the rule really does fire when the turn is a real user turn."""
    agent = _agent()
    batch = BatchInput(
        texts=[
            TextData(
                source=TextSource.INPUT,
                content="自然地接續話題，確認背後有沒有什麼值得一提的細節。",
            )
        ],
    )

    messages = agent._to_messages(batch)

    assert "不是答案" in _user_text(messages)


