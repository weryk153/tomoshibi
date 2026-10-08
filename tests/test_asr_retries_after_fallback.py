"""選的辨識引擎載入失敗、退回 sherpa-onnx 之後，下一次重新載入要再試一次選的那個。

faster-whisper 沒裝時後端退回 sherpa-onnx；使用者在設定頁一鍵裝好、重新載入，設定
沒變（還是 faster_whisper），以前就判定「同樣的設定、不用重建」，一直用 sherpa-onnx。
"""

from types import SimpleNamespace

from src.open_llm_vtuber import service_context as module
from src.open_llm_vtuber.service_context import ServiceContext


def _asr_config():
    block = SimpleNamespace(model_dump=lambda: {})
    return SimpleNamespace(
        asr_model="faster_whisper", faster_whisper=block, sherpa_onnx_asr=block
    )


def test_a_fallback_engine_is_replaced_once_the_chosen_one_loads(monkeypatch):
    installed = {"faster_whisper": False}
    builds = []

    def build(name, **options):
        builds.append(name)
        if name == "faster_whisper" and not installed["faster_whisper"]:
            raise ModuleNotFoundError("No module named 'faster_whisper'")
        return SimpleNamespace(kind=name)  # 真的引擎沒有名字可以問

    monkeypatch.setattr(module.ASRFactory, "get_asr_system", staticmethod(build))
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(player_language="")
    context.character_config = SimpleNamespace(asr_config=None)
    context.asr_engine = None

    config = _asr_config()
    context.init_asr(config)
    assert context.asr_engine.kind == "sherpa_onnx_asr"

    installed["faster_whisper"] = True
    context.init_asr(config)  # 同一份設定：重新載入
    assert context.asr_engine.kind == "faster_whisper"

    count = len(builds)
    context.init_asr(config)  # 已經是選的那個：不重建
    assert context.asr_engine.kind == "faster_whisper" and len(builds) == count
