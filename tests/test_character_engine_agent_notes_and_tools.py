"""主機給 agent 的備註通道，和模式開著時才存在的工具。"""

from ai_character_engine.tools.models import ToolDefinition

from tests.test_engine_agent import EngineLLM, agent, batch, companion

TOOL = ToolDefinition(
    name="minecraft_do",
    description="x",
    parameters={"type": "object", "properties": {}, "required": []},
)


def test_notes_in_metadata_reach_the_turn(tmp_path):
    a = agent(companion(tmp_path, EngineLLM()))
    text, notes = a._turn(
        batch("嗨", notes=["遊戲裡剛發生：\n- 天黑了", "目前狀態：血量 9/20"]), ()
    )
    assert text == "嗨"
    assert "天黑了" in "\n".join(notes) and "9/20" in "\n".join(notes)


def test_add_tool_registers_now_if_already_synced_and_survives_resync(tmp_path):
    source = companion(tmp_path, EngineLLM())
    a = agent(source)
    a._bring_up_to_date(source)
    companion_tools = source.tools
    assert "minecraft_do" not in companion_tools

    async def handler(**_):
        return "ok"

    a.add_tool(TOOL, handler)
    assert "minecraft_do" in companion_tools
    a.add_tool(TOOL, handler)  # 重複加不炸、不重複
    assert sum(1 for t in companion_tools if t.definition.name == "minecraft_do") == 1
    other = agent(source)
    other._bring_up_to_date(source)  # 別的 agent 接手會清掉
    assert "minecraft_do" not in companion_tools
    a._bring_up_to_date(source)  # 自己接回來要補回
    assert "minecraft_do" in companion_tools
    a.remove_tool("minecraft_do")
    assert "minecraft_do" not in companion_tools
    a._bring_up_to_date(source)
    assert "minecraft_do" not in companion_tools


def test_add_tool_before_first_sync_registers_on_sync(tmp_path):
    source = companion(tmp_path, EngineLLM())
    a = agent(source)

    async def handler(**_):
        return "ok"

    a.add_tool(TOOL, handler)
    assert "minecraft_do" not in source.tools
    a._bring_up_to_date(source)
    assert "minecraft_do" in source.tools
