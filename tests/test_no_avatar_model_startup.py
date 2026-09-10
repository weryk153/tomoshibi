"""沒有頭像模型時，開機不能炸。

init_live2d 載入模型失敗時會記一行「Try to proceed without Live2D...」然後把
live2d_model 留成 None 繼續跑。但 construct_system_prompt 裡的動作／表情 prompt
判斷每一條都會去讀 live2d_model 的屬性，於是「繼續跑」實際上是在初始化階段
AttributeError，整個後端直接結束。

真實觸發過：全新的工作目錄沒有 model_dict.json（它不進版控，只有角色 API 讀取
時才會從 config_templates 補），開機時 AvatarModel 找不到檔案 → None → 炸掉。
桌面版第一次啟動就是這個狀況。兩件事分別修：run_server 開機時先補檔，
construct_system_prompt 在沒有模型時跳過那三份 prompt。
"""

import asyncio
import inspect
from types import SimpleNamespace

import run_server
from src.open_llm_vtuber.service_context import ServiceContext

AVATAR_PROMPTS = (
    "live2d_motion_prompt",
    "vrm_motion_prompt",
    "live2d_expression_prompt",
)


class _Recorder:
    def __init__(self):
        self.requested: list[str] = []

    def load_util(self, name: str) -> str:
        self.requested.append(name)
        return f"<<{name}>>"


def test_system_prompt_builds_without_an_avatar_model(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr("src.open_llm_vtuber.service_context.prompt_loader", rec)

    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(
        tool_prompts={name: name for name in AVATAR_PROMPTS},
        player_language="",
        player_prompt="",
    )
    context.live2d_model = None
    context.character_config = SimpleNamespace(
        long_term_memory_enabled=False, conf_uid="test"
    )
    context.stage_director_prompt = ""

    prompt = asyncio.run(context.construct_system_prompt("persona"))

    assert "persona" in prompt
    assert not set(rec.requested) & set(AVATAR_PROMPTS), (
        "沒有模型時不該載入描述模型表情／動作的 prompt"
    )


def test_server_seeds_model_dict_before_building_the_server():
    src = inspect.getsource(run_server.run)
    seed = src.find("_ensure_model_dict()")
    build = src.find("WebSocketServer(config=config)")
    assert seed != -1, "run_server 開機時沒有補 model_dict.json"
    assert seed < build, "要在建立 server（載入頭像模型）之前補，否則照樣找不到檔案"
