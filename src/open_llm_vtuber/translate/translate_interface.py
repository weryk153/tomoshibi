import abc


class UnspeakableTranslation(Exception):
    """翻譯器確定這句沒有可念的譯文——重試過了，回來的還是別的語言。

    語音翻譯的呼叫端接到這個就讓那句靜音（字幕照顯示），而不是拿原文或錯的
    語言去合成：用日文聲線唸中文或英文，聽起來都不對。其他失敗（連線、逾時）
    照舊退回原文，不走這條路。
    """


class TranslateInterface(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def translate(self, text: str) -> str:
        """
        Translate the input text to the target language."""
        raise NotImplementedError
