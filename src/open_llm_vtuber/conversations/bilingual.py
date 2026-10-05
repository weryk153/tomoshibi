"""雙語字幕：畫面字幕上多一行她實際唸出來的那句。

角色頁「語言」區的開關（角色設定 ``bilingual_subtitle``），預設關。開著時，
音訊 payload 多帶 ``spoken_text``，前端畫成兩行：上行是念的、下行是原本的字幕。
對話紀錄與記憶只看 ``display_text.text``，這裡完全不碰。
"""

from __future__ import annotations

from typing import Optional


def spoken_line(
    enabled: bool,
    *,
    original_tts: str,
    tts_text: str,
    display: str,
    subtitle: str,
) -> Optional[str]:
    """這句要不要多帶「她念的那句」；不帶時回 None。

    只有真的經過翻譯（語音被翻成她的語言、或字幕被翻成你看的語言）才算兩種
    語言。沒翻譯時念的那句只是過濾過的顯示文字（星號動作、表情符號拿掉了），
    多一行幾乎一樣的字只是雜訊——所以不能直接比 ``tts_text`` 跟顯示的字。
    """
    if not enabled:
        return None
    voice_translated = tts_text != original_tts
    subtitle_translated = subtitle != display
    if not (voice_translated or subtitle_translated):
        return None
    spoken = tts_text.strip()
    if not spoken or spoken == subtitle.strip():
        return None
    return spoken
