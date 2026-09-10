from dataclasses import dataclass, asdict
from typing import List, Optional
from abc import ABC, abstractmethod


@dataclass
class Actions:
    """Represents actions that can be performed alongside text output"""

    expressions: Optional[List[str] | List[int]] = None
    # 跟 expressions 一一對應的強度（0..1）。只有 VRM 用得到——它的表情是連續
    # 權重；Live2D 的表情是獨立檔案，沒有「七成的笑」。
    expression_intensities: Optional[List[float]] = None
    motions: Optional[List[dict]] = None
    pictures: Optional[List[str]] = None
    sounds: Optional[List[str]] = None
    stage_performance: Optional[str] = None
    # 這一則回覆的情緒關鍵字（名字）。表情用的是 expressions 裡的索引；這個欄位
    # 是給語音挑參考音用的，兩者刻意分開，因為索引反查名字有歧義。
    emotion: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert Actions object to a dictionary for JSON serialization"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class BaseOutput(ABC):
    """Base class for agent outputs that can be iterated"""

    @abstractmethod
    def __aiter__(self):
        """Make the output iterable"""
        pass


@dataclass
class DisplayText:
    """Text to be displayed with optional metadata"""

    text: str
    name: Optional[str] = "AI"  # Keep the name field for frontend display
    avatar: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {"text": self.text, "name": self.name, "avatar": self.avatar}

    def __str__(self) -> str:
        """String representation for logging"""
        return f"{self.name}: {self.text}"


@dataclass
class SentenceOutput(BaseOutput):
    """
    Output type for text-based responses.
    Contains a single sentence pair (display and TTS) with associated actions.

    Attributes:
        display_text: Text to be displayed in UI
        tts_text: Text to be sent to TTS engine
        actions: Associated actions (expressions, pictures, sounds)
    """

    display_text: DisplayText  # Changed from str to DisplayText
    tts_text: str  # Text for TTS
    actions: Actions

    async def __aiter__(self):
        """Yield the sentence pair and actions"""
        yield self.display_text, self.tts_text, self.actions


@dataclass
class AudioOutput(BaseOutput):
    """Output type for audio-based responses"""

    audio_path: str
    display_text: DisplayText  # Changed from str to DisplayText
    transcript: str  # Original transcript
    actions: Actions

    async def __aiter__(self):
        """Iterate through audio segments and their actions"""
        yield self.audio_path, self.display_text, self.transcript, self.actions
