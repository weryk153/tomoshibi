"""character_engine_agent：前景照舊，AI Character Engine 負責對話之後的認知。

繼承 BasicMemoryAgent 而不是重寫一個走引擎前景的 agent，理由有實測依據（見
docs/superpowers/specs/2026-09-28-character-engine-agent-design.md）：引擎在有工具
定義時會把串流文字扣到整輪結束才送出、訊息只有文字所以影像要多過一次模型，而
這個專案開著 MCP 工具、也用鏡頭。換過去每一輪的第一句都會變慢。

所以這裡只做三件事：

- 每一輪把引擎那邊的狀態、目標、體會接在最新一句使用者訊息後面（只送給模型，
  不存進記憶）。
- 她生成回覆的期間，告訴引擎背景工作要讓路。
- 每一輪結束後，把這一輪交給引擎（observe_turn，由 single_conversation 呼叫）。

這個模組不匯入引擎。引擎沒裝的時候 agent_factory 會直接丟出寫明做法的錯誤，
不會建出這個 agent；工作階段查不到的時候（provider 不相容、被換掉的空檔）她的
行為跟 BasicMemoryAgent 完全一樣。
"""

import asyncio
from typing import Any, Callable, Optional, Union

from loguru import logger

from ...character_engine.prompt_block import build_engine_block
from .basic_memory_agent import BasicMemoryAgent


# 接在使用者的話後面，所以要講明這不是對方說的——不然她會回應它。
ENGINE_NOTE = "\n\n［以下不是對方說的話，是你自己此刻的狀態與心事，只有你知道］"


class CharacterEngineAgent(BasicMemoryAgent):
    def __init__(
        self,
        *,
        session: Union[None, Any, Callable[[], Any]] = None,
        character_name: str = "",
        **basic,
    ):
        """session 可以是工作階段本身，或是一個每次回傳「目前那一個」的函式。

        正式執行時給的是函式：這個 agent 是所有連線共用的，而每次儲存設定都會
        建一個新的 agent、必要時換一個工作階段。舊的 agent 還被別的連線拿著，
        它得跟著換。
        """
        # BasicMemoryAgent.__init__ 會呼叫 _chat_function_factory，它被這裡覆寫了，
        # 所以這幾個欄位必須先存在。
        self._session_source = session
        self._character_name = character_name
        self._observations: set = set()
        super().__init__(**basic)

    def _current_session(self) -> Optional[Any]:
        source = self._session_source
        if source is None or hasattr(source, "observe_turn"):
            return source
        try:
            return source()
        except Exception as exc:
            logger.warning(
                f"[engine] session lookup failed ({type(exc).__name__}: {exc})"
            )
            return None

    def _tell_session(self, signal: str, *arguments) -> None:
        notify = getattr(self._current_session(), signal, None)
        if notify is None:
            return
        try:
            notify(*arguments)
        except Exception as exc:
            logger.warning(f"[engine] {signal} failed ({type(exc).__name__}: {exc})")

    # --- 送給模型的內容 -----------------------------------------------------

    def _engine_block(self) -> str:
        session = self._current_session()
        if session is None:
            return ""
        try:
            return build_engine_block(
                session.snapshot(), character_name=self._character_name
            )
        except Exception as exc:
            logger.warning(f"[engine] state not injected ({type(exc).__name__}: {exc})")
            return ""

    def _to_messages(self, input_data):
        """把她此刻的狀態接在最新一句使用者訊息後面。

        不放系統提示，是量出來的：系統提示一變，推論端就得把它後面整段對話歷史
        重新讀一遍。7 輪對話時，狀態放系統提示尾端、心情每輪在變，第一個字要
        4.5 秒；接在最新一句後面是 1.0 秒（不放是 0.9 秒）。而且對話越長差越多。

        super() 已經把使用者的原話存進記憶了，這裡改的只是這一次送出去的那份——
        跟 build_turn_guidance 是同一種做法。狀態留在記憶裡的話，下一輪她會讀到
        一句「使用者說：心情：開心」。
        """
        messages = super()._to_messages(input_data)
        block = self._engine_block()
        if not block or not messages or messages[-1].get("role") != "user":
            return messages
        note = ENGINE_NOTE + block
        newest = messages[-1]
        content = newest.get("content")
        if isinstance(content, str):
            messages[-1] = {**newest, "content": content + note}
        elif isinstance(content, list):
            parts = [dict(part) for part in content]
            for part in reversed(parts):
                if part.get("type") == "text":
                    part["text"] = str(part.get("text", "")) + note
                    break
            else:
                parts.append({"type": "text", "text": note.lstrip()})
            messages[-1] = {**newest, "content": parts}
        return messages

    def _chat_function_factory(self):
        chat_with_memory = super()._chat_function_factory()

        async def chat_with_engine(input_data):
            # 背景工作跟她用同一顆模型；她講話的時候背景讓路。開始與結束必須問
            # 同一個工作階段（中途可能被換掉），而且 finally 是必要的：被打斷時
            # 這個 generator 會在半途被關掉，沒放手的話背景認知就停住了。
            session = self._current_session()
            started = getattr(session, "foreground_started", None)
            finished = getattr(session, "foreground_finished", None)
            if started is not None:
                started()
            try:
                async for output in chat_with_memory(input_data):
                    yield output
            finally:
                if finished is not None:
                    finished()

        return chat_with_engine

    # --- 對話 ---------------------------------------------------------------

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        super().set_memory_from_history(conf_uid, history_uid)
        self._tell_session(
            "bind_conversation",
            history_uid,
            [(m["role"], m["content"]) for m in self._memory],
        )

    def observe_turn(
        self, conf_uid: str, history_uid: str, user_text: str, reply: str
    ) -> None:
        """一輪講完後呼叫。fire-and-forget：不等、不丟例外。"""
        session = self._current_session()
        if session is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._observe(session, history_uid, user_text, reply))
        # 留著 reference：asyncio 只弱參考 task，沒人拿著的話可能跑到一半被回收。
        self._observations.add(task)
        task.add_done_callback(self._observations.discard)

    async def _observe(
        self, session: Any, history_uid: str, user_text: str, reply: str
    ) -> None:
        try:
            # 每一輪都指明是哪段對話：兩個連線可以在不同的對話裡輪流講。
            await session.observe_turn(user_text, reply, history_uid=history_uid)
        except Exception as exc:
            logger.warning(f"[engine] turn not observed ({type(exc).__name__}: {exc})")

    async def close(self) -> None:
        """一個連線結束時由 ServiceContext.close() 呼叫。

        agent 是所有連線共用的，所以這裡不能把認知工作階段關掉——那樣重新整理一次
        頁面之後，引擎就再也收不到任何一輪。只等這個連線交出去的那幾輪記完、
        把狀態存檔；背景工作留著繼續跑。
        """
        if self._observations:
            await asyncio.gather(*tuple(self._observations), return_exceptions=True)
        self._tell_session("flush")
