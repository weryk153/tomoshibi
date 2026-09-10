from typing import Type
from .vad_interface import VADInterface
from ..utils.optional_deps import reraise_if_torch_missing


class VADFactory:
    @staticmethod
    def get_vad_engine(engine_type, **kwargs) -> Type[VADInterface]:
        if engine_type is None:
            return None
        if engine_type == "silero_vad":
            try:
                from .silero import VADEngine as SileroVADEngine
            except ModuleNotFoundError as e:
                reraise_if_torch_missing(e, "silero_vad")

            return SileroVADEngine(
                kwargs.get("orig_sr"),
                kwargs.get("target_sr"),
                kwargs.get("prob_threshold"),
                kwargs.get("db_threshold"),
                kwargs.get("required_hits"),
                kwargs.get("required_misses"),
                kwargs.get("smoothing_window"),
            )
