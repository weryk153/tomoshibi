"""認知工作階段：把每一輪對話交給 AI Character Engine，提交它的背景結果並存檔。

前景對話不走引擎（理由見規格），所以這裡把引擎當成「對話之後的認知」來用：

1. 一輪講完，用引擎的前景路徑記下這一輪。引擎的 LLM 位置放一個只回傳既有回覆的
   client——引擎因此照它自己的規則推進版本、套用狀態規則、記事件，但不會多呼叫
   一次模型。
2. 引擎排背景工作（情緒、記憶、目標、反思、摘要）。
3. 背景結果回來後提交；過期的在界限內改掛到目前的版本。

整段對對話是 fire-and-forget：observe_turn 裡任何失敗只寫 log。

這個模組只在選了 character_engine_agent 時才會被匯入，所以可以在最上面匯入引擎。
見 docs/superpowers/specs/2026-09-28-character-engine-agent-design.md。
"""

import asyncio
import heapq
import itertools
import json
import os
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from ai_character_engine import (
    BackgroundCognitionConfig,
    BackgroundCognitionKind,
    BackgroundCognitionRuntime,
    BackgroundWorkerSpec,
    CharacterEvent,
    CharacterProfile,
    CharacterRuntime,
    CharacterState,
    CognitiveCommitCoordinator,
    CognitiveModelRouter,
    CognitiveModelRuntime,
    CognitiveRole,
    CognitiveRolePolicy,
    CommitStatus,
    ContextBudget,
    GoalManager,
    JsonlGoalStore,
    JsonlLongTermCognitionStore,
    LongTermCognitionManager,
    MemoryManager,
    ModelEndpoint,
    MultiTaskRuntime,
    MultiTaskRuntimeConfig,
    StalePolicy,
    StatePatch,
    TaskPriority,
)

# 這三個不在引擎的穩定 root API 裡，只能從實作模組匯入。
from ai_character_engine.context.builder import ContextBuilder
from ai_character_engine.llm.models import LLMResponse, Message
from ai_character_engine.memory.store import JsonlMemoryStore
from ai_character_engine.session.serialization import state_from_dict, state_to_dict
from loguru import logger

from .prompt_block import CharacterSnapshot
from .state_policy import next_state_change

APPLIED_OBSERVATION_KEY = "tomoshibi_applied_observation"
OBSERVATION_KEY = "observed_user_emotion"
MIRROR_HISTORY_MESSAGES = 24
SEED_HISTORY_MESSAGES = 12
# 同時記著幾段對話最近的話。兩個連線可以在不同的對話裡輪流講。
MIRRORED_CONVERSATIONS = 8

MEMORY_TARGET = "memory.append_candidate"
# 這兩種寫進引擎的記憶，而引擎的記憶是跟著對話走的。
CONVERSATION_SCOPED_TARGETS = (MEMORY_TARGET, "memory.conversation_summary_candidate")


@dataclass(frozen=True)
class _Worker:
    name: str
    kind: BackgroundCognitionKind
    role: CognitiveRole
    priority: TaskPriority
    target: str

    @property
    def setting(self) -> str:
        return f"{self.name}_every"


# 由急到緩，順序就是用模型的優先序。情緒排最前面：它決定下一句回覆的心情，
# 晚到就沒用了。
_WORKERS = (
    _Worker(
        "emotion",
        BackgroundCognitionKind.EMOTION_ANALYSIS,
        CognitiveRole.EMOTION,
        TaskPriority.HIGH,
        "state.emotion_candidate",
    ),
    _Worker(
        "memory",
        BackgroundCognitionKind.MEMORY_EXTRACTION,
        CognitiveRole.MEMORY,
        TaskPriority.HIGH,
        MEMORY_TARGET,
    ),
    _Worker(
        "goal",
        BackgroundCognitionKind.GOAL_MOTIVATION,
        CognitiveRole.GOAL,
        TaskPriority.NORMAL,
        "cognition.goal_candidate",
    ),
    _Worker(
        "reflection",
        BackgroundCognitionKind.REFLECTION,
        CognitiveRole.REFLECTION,
        TaskPriority.LOW,
        "cognition.reflection_candidate",
    ),
    _Worker(
        "summary",
        BackgroundCognitionKind.CONVERSATION_SUMMARY,
        CognitiveRole.SUMMARY,
        TaskPriority.LOW,
        "memory.conversation_summary_candidate",
    ),
)


@dataclass(frozen=True)
class CognitionSettings:
    """每種背景工作每幾輪跑一次；0 是停用。

    預設值來自實測（qwen/qwen3.5-9b、M4 16GB）。每次呼叫約：情緒 7 秒、記憶 5 秒、
    目標 10–20 秒、反思 12 秒、摘要 15 秒；而一輪對話（回覆加上使用者打字）大約
    18 秒，同一顆模型還要生成回覆、翻譯字幕、整理 core_memory。第一版的預設
    （1/1/3/5/2）平均每輪要 27 秒，8 輪對話結束時積了 7 個沒跑的工作。

    - 情緒每輪跑：它決定下一句的心情。
    - 記憶每 2 輪跑一次，一次涵蓋這兩輪。
    - 摘要預設停用：它只寫進引擎的記憶，而那份記憶這一版不注入提示。
    """

    emotion_every: int = 1
    memory_every: int = 2
    summary_every: int = 0
    reflection_every: int = 6
    goal_every: int = 4
    # 一次模型呼叫最多等多久。引擎的預設（情緒 12 秒、摘要 20 秒）在這台機器上
    # 實測會逾時。
    timeout_seconds: float = 60.0
    # 背景結果落後幾輪以內還算數。見規格「過期的處理」。
    max_rebase_turns: int = 3
    # 引擎的目標沒有自動到期；超過這個天數沒更新的不再寫進提示。
    goal_max_age_days: int = 7
    # 她在講話時背景工作會讓路。對話沒回報講完（例外、斷線）的話，過這麼久就
    # 當作講完了——不然背景認知會永遠停在那裡，而且沒有任何徵兆。
    foreground_patience_seconds: float = 120.0

    def __post_init__(self) -> None:
        for name in (
            "emotion_every",
            "memory_every",
            "summary_every",
            "reflection_every",
            "goal_every",
            "max_rebase_turns",
            "goal_max_age_days",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.foreground_patience_seconds <= 0:
            raise ValueError("foreground_patience_seconds must be > 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")


class _ModelAccess:
    """同一顆本機模型誰先用。每一條規則都是量出來的：

    - 背景跟對話同時跑，第一句回覆的延遲中位數從 2.6 秒變成 4.7 秒、最長 12 秒。
      所以她開始生成回覆時背景讓路，正在跑的那一次放棄、之後重來。
    - 情緒分析有自己的通道，不跟其他背景工作排隊。它決定下一句的心情，而且短
      （約 7 秒）。讓它排隊的兩個版本，8 輪都只提交了 3 次：她講完的那一刻，上一輪
      被打斷的工作先拿到模型，這一輪的情緒要等對話收尾才排得進來。
    - 其餘的工作一次一個，依優先序。
    - 每個工作最多被她打斷一次。目標和反思一次要 10 到 20 秒，比兩輪對話之間的
      空檔還長，每次都打斷重來的話永遠跑不完。第二次就讓它跟她同時跑完。
    """

    def __init__(self, patience_seconds: float) -> None:
        self._patience = patience_seconds
        self._talking = 0
        self._generation = 0
        self._quiet = asyncio.Event()
        self._quiet.set()
        self._interrupted = asyncio.Event()
        self._busy = False
        self._waiting: list = []
        self._ticket = itertools.count()

    # --- 前景 ---

    def foreground_started(self) -> None:
        self._talking += 1
        self._generation += 1
        self._quiet.clear()
        self._interrupted.set()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        # 計時放在這裡，不放在等待的那一端：等待的工作自己會先逾時，輪不到它來
        # 發現沒人回報講完（審查抓到的，預設值下安全網永遠不會觸發）。
        loop.call_later(self._patience, self._give_up_waiting_for, self._generation)

    def foreground_finished(self) -> None:
        self._talking = max(0, self._talking - 1)
        if self._talking == 0:
            self._quiet.set()
            self._interrupted.clear()

    def _give_up_waiting_for(self, generation: int) -> None:
        if self._talking and generation == self._generation:
            logger.warning(
                f"[engine] no end-of-reply signal for {self._patience:.0f}s; "
                "resuming background work"
            )
            self._talking = 0
            self.foreground_finished()

    # --- 背景 ---

    async def _take_turn(self, rank: int) -> None:
        if not self._busy and not self._waiting:
            self._busy = True
            return
        ready = asyncio.get_running_loop().create_future()
        entry = (rank, next(self._ticket), ready)
        heapq.heappush(self._waiting, entry)
        try:
            await ready
        except asyncio.CancelledError:
            if ready.done() and not ready.cancelled():
                self._pass_on()  # 輪到了才被取消：把位子讓給下一個
            elif entry in self._waiting:
                # 可能已經不在名單裡：_pass_on 會順手丟掉被取消的。這裡再丟出別的
                # 例外的話會蓋掉 CancelledError，引擎就以為這個工作只是失敗了。
                self._waiting.remove(entry)
                heapq.heapify(self._waiting)
            raise

    def _pass_on(self) -> None:
        while self._waiting:
            _, _, ready = heapq.heappop(self._waiting)
            if not ready.done():
                ready.set_result(None)
                return
        self._busy = False

    async def call(
        self,
        rank: int,
        make_call: Callable[[], Any],
        timeout: float,
        *,
        own_lane: bool = False,
    ):
        given_way = False
        while True:
            await self._quiet.wait()
            if not own_lane:
                await self._take_turn(rank)
            try:
                if not self._quiet.is_set():
                    continue  # 等位子的時候她開口了
                call = asyncio.ensure_future(make_call())
                watching = (
                    []
                    if given_way
                    else [asyncio.ensure_future(self._interrupted.wait())]
                )
                try:
                    done, _ = await asyncio.wait(
                        {call, *watching},
                        timeout=timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    for watcher in watching:
                        watcher.cancel()
                    if not call.done():
                        call.cancel()
                        await asyncio.gather(call, return_exceptions=True)
                if call in done and not call.cancelled():
                    return call.result()
                if not done:
                    raise TimeoutError(f"model call exceeded {timeout:.0f}s")
                given_way = True
            finally:
                if not own_lane:
                    self._pass_on()


class _PoliteClient:
    """背景模型的包裝：每一次呼叫都經過 _ModelAccess。"""

    def __init__(
        self,
        inner: Any,
        access: _ModelAccess,
        rank: int,
        timeout: float,
        own_lane: bool,
    ):
        self._inner = inner
        self._access = access
        self._rank = rank
        self._timeout = timeout
        self._own_lane = own_lane

    async def generate(self, messages, *, tools=None):
        return await self._access.call(
            self._rank,
            lambda: self._inner.generate(messages, tools=tools),
            self._timeout,
            own_lane=self._own_lane,
        )


class _ReplayClient:
    """引擎的「前景模型」：回傳 Tomoshibi 已經講完的那句話。"""

    def __init__(self) -> None:
        self.reply = ""

    async def generate(self, messages, *, tools=None) -> LLMResponse:
        return LLMResponse(text=self.reply, model="tomoshibi-foreground")


def _relationship_patch(state, *, count_turn: bool) -> Optional[StatePatch]:
    change = next_state_change(
        trust=state.trust,
        favorability=state.favorability,
        relationship_stage=state.relationship_stage,
        observation=state.custom.get(OBSERVATION_KEY),
        applied_observation_id=state.custom.get(APPLIED_OBSERVATION_KEY),
        count_turn=count_turn,
    )
    patch = StatePatch(
        emotion=change.emotion,
        trust_delta=change.trust_delta,
        favorability_delta=change.favorability_delta,
        relationship_stage=change.relationship_stage,
        custom_updates=(
            {APPLIED_OBSERVATION_KEY: change.applied_observation_id}
            if change.applied_observation_id
            else {}
        ),
        reason="tomoshibi relationship rules",
    )
    return None if patch.is_noop else patch


class _BackgroundExtractionOnly:
    """引擎的 MemoryWritePolicy：前景不寫記憶。

    引擎預設會在前景替每一輪寫一筆「User said: <原話> State changed: …」，而提交
    協調器看到同一輪已經有記憶，就把背景擷取出來的那幾筆判成衝突丟掉——留下來的
    反而是品質比較差的那一筆。關掉前景寫入，讓背景擷取成為唯一的來源。
    """

    def importance(self, *, event, response, state_before, state_after):
        return None


class _RelationshipPolicy:
    """引擎的 CharacterStatePolicy：每記下一輪使用者的話就套一次規則。"""

    def on_event(self, event, state):
        if event.type != "user_message":
            return None
        return _relationship_patch(state, count_turn=True)

    def on_tool_result(self, result, state):
        return None


def _clean_history(messages: Sequence[tuple[str, str]]) -> list[Message]:
    """跟 BasicMemoryAgent.set_memory_from_history 同一套整理：只留 user／assistant、
    去掉連續同角色、開頭必須是 user。"""
    cleaned: list[Message] = []
    for role, content in messages:
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        if cleaned and cleaned[-1].role == role:
            continue
        cleaned.append(Message(role, content))
    cleaned = cleaned[-SEED_HISTORY_MESSAGES:]
    while cleaned and cleaned[0].role != "user":
        cleaned.pop(0)
    return cleaned


class CognitionSession:
    def __init__(
        self,
        *,
        storage_dir: Path,
        character_id: str,
        character_name: str,
        client_for_role: Callable[[str], Any],
        settings: Optional[CognitionSettings] = None,
    ) -> None:
        self.settings = settings or CognitionSettings()
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._character_id = character_id
        self._bound: Optional[str] = None
        self._active: Optional[str] = None
        self._mirrors: "OrderedDict[str, list[Message]]" = OrderedDict()
        self._seeds: dict[str, list[Message]] = {}
        self._replay = _ReplayClient()
        self._turn_lock = asyncio.Lock()
        self._pending: set[asyncio.Task] = set()
        self._closed = False
        self._retired = False
        self._access = _ModelAccess(self.settings.foreground_patience_seconds)
        self._every_by_target: dict[str, int] = {}
        self._live_by_kind: dict[BackgroundCognitionKind, list] = {}
        self._history_by_task: dict[str, Optional[str]] = {}
        try:
            self._loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        state = CharacterState()
        state_file = self._state_file()
        if state_file.is_file():
            try:
                state.restore(
                    state_from_dict(json.loads(state_file.read_text("utf-8")))
                )
            except Exception as exc:
                # 壞掉的狀態檔不可以讓 agent 起不來；從預設值重新累積。
                logger.warning(f"[engine] state file unreadable, starting fresh: {exc}")

        self.runtime = CharacterRuntime(
            character=CharacterProfile(
                id=character_id,
                name=character_name or character_id,
                description=character_name,
            ),
            llm=self._replay,
            state=state,
            state_policy=_RelationshipPolicy(),
            memory_manager=MemoryManager(
                store=JsonlMemoryStore(self._dir / "memory.jsonl"),
                write_policy=_BackgroundExtractionOnly(),
            ),
            goal_manager=GoalManager(store=JsonlGoalStore(self._dir / "goals.jsonl")),
            long_term_cognition=LongTermCognitionManager(
                store=JsonlLongTermCognitionStore(self._dir / "cognition.jsonl")
            ),
            # 這裡組出來的 prompt 不會送給任何模型，預算只會造成誤判的失敗
            # （使用者貼一大段文字就超過預設的 8192）。
            context_builder=ContextBuilder(
                budget=ContextBudget(
                    context_window_tokens=10_000_000, reserved_output_tokens=1
                )
            ),
            max_history_messages=MIRROR_HISTORY_MESSAGES,
            memory_scope_id=character_id,
            cognition_scope_id=character_id,
            goal_scope_id=character_id,
        )
        enabled = [
            worker
            for worker in _WORKERS
            if int(getattr(self.settings, worker.setting)) > 0
        ]
        # 每一種工作各有一個位子，誰先用模型由 _ModelAccess 決定。只有一個位子的話，
        # 被她打斷、等著重來的那個工作會擋住後面所有的工作。
        self._tasks = MultiTaskRuntime(
            self.runtime,
            config=MultiTaskRuntimeConfig(worker_count=max(1, len(enabled))),
        )
        self._background = self._build_background(enabled, client_for_role)
        self._commits = CognitiveCommitCoordinator(self._tasks)
        for target, policy in tuple(self._commits.policies.items()):
            self._commits.policies[target] = replace(
                policy, stale_policy=StalePolicy.ALLOW_MANUAL_REBASE
            )

    # --- 組裝 ---------------------------------------------------------------

    def _build_background(
        self, enabled, client_for_role
    ) -> Optional[BackgroundCognitionRuntime]:
        specs, endpoints, policies = [], [], {}
        for rank, worker in enumerate(enabled):
            client = client_for_role(worker.name)
            if client is None:
                continue
            every = int(getattr(self.settings, worker.setting))
            specs.append(
                BackgroundWorkerSpec(
                    worker.kind,
                    priority=worker.priority,
                    # 引擎的逾時連「等她講完、等輪到自己」的時間一起算，所以放寬；
                    # 模型呼叫本身的逾時由 _ModelAccess 管。
                    timeout_s=self.settings.timeout_seconds
                    + self.settings.foreground_patience_seconds,
                    every_n_revisions=every,
                )
            )
            self._every_by_target[worker.target] = every
            endpoint_id = f"tomoshibi-{worker.name}"
            endpoints.append(
                ModelEndpoint(
                    endpoint_id=endpoint_id,
                    client=_PoliteClient(
                        client,
                        self._access,
                        rank,
                        self.settings.timeout_seconds,
                        own_lane=worker.name == "emotion",
                    ),
                )
            )
            policies[worker.role] = CognitiveRolePolicy(
                primary_endpoint_ids=(endpoint_id,)
            )
        if not specs:
            return None
        return BackgroundCognitionRuntime(
            self._tasks,
            CognitiveModelRuntime(
                endpoints=tuple(endpoints),
                router=CognitiveModelRouter(policies=policies),
            ),
            config=BackgroundCognitionConfig(
                worker_specs=tuple(specs), history_messages=SEED_HISTORY_MESSAGES
            ),
        )

    def _state_file(self) -> Path:
        return self._dir / "state.json"

    def _save_state(self) -> None:
        if self._retired:
            return
        payload = json.dumps(
            state_to_dict(self.runtime.state.snapshot()), ensure_ascii=False, indent=2
        )
        temporary = self._state_file().with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self._state_file())

    def _scope(self, history_uid: Optional[str]) -> str:
        """引擎的記憶跟著對話走（跟 core_memory.md 一樣），狀態、目標、體會屬於角色。"""
        if not history_uid:
            return self._character_id
        return f"{self._character_id}:{history_uid}"

    def usable_in_running_loop(self) -> bool:
        if self._closed:
            return False
        try:
            return self._loop is None or self._loop is asyncio.get_running_loop()
        except RuntimeError:
            return self._loop is None

    # --- 對話 ---------------------------------------------------------------

    def bind_conversation(
        self, history_uid: str, recent: Sequence[tuple[str, str]]
    ) -> None:
        """載入一段對話時呼叫：之後沒指明對話的那幾輪算它的。

        recent 只在引擎還沒看過這段對話時才用得上。看過的話引擎手上的比較新——
        重新整理頁面會再載入一次歷史，拿它蓋掉的話剛記下的那幾輪就不見了。
        """
        self._bound = history_uid
        if history_uid != self._active and history_uid not in self._mirrors:
            self._seeds[history_uid] = _clean_history(recent)

    def _switch_to(self, history_uid: Optional[str]) -> None:
        """必須在 _turn_lock 裡呼叫。"""
        if history_uid != self._active:
            if self._active is not None:
                self._mirrors[self._active] = list(self.runtime.history)
                self._mirrors.move_to_end(self._active)
                while len(self._mirrors) > MIRRORED_CONVERSATIONS:
                    self._mirrors.popitem(last=False)
            kept = self._mirrors.pop(history_uid, None) if history_uid else None
            if kept is None:
                kept = self._seeds.pop(history_uid, []) if history_uid else []
            self.runtime.history = list(kept)
            self._active = history_uid
        self.runtime.memory_scope_id = self._scope(history_uid)

    def foreground_started(self) -> None:
        """她開始生成回覆。背景工作從現在起讓路。"""
        self._access.foreground_started()

    def foreground_finished(self) -> None:
        self._access.foreground_finished()

    async def observe_turn(
        self, user_text: str, reply: str, *, history_uid: Optional[str] = None
    ) -> None:
        if (
            self._closed
            or not str(user_text or "").strip()
            or not str(reply or "").strip()
        ):
            return
        conversation = history_uid if history_uid is not None else self._bound
        try:
            async with self._turn_lock:
                self._switch_to(conversation)
                self._replay.reply = reply
                result = await self._tasks.run_foreground(
                    CharacterEvent.user_message(user_text)
                )
                handles = (
                    await self._background.schedule_after_foreground(result)
                    if self._background is not None
                    else ()
                )
                self._abandon_jobs_made_obsolete_by(handles)
                self._save_state()
            for handle in handles:
                self._history_by_task[handle.task_id] = conversation
                task = asyncio.create_task(self._collect(handle))
                self._pending.add(task)
                task.add_done_callback(self._pending.discard)
        except Exception as exc:
            logger.warning(f"[engine] turn not recorded ({type(exc).__name__}: {exc})")

    def _abandon_jobs_made_obsolete_by(self, handles) -> None:
        """同一種工作排了新的，舊的就不用跑了——不管它在排隊還是已經在跑。

        使用者講得比背景快的時候，舊的跑完也只會讓路給新的（見 _superseded），
        白白佔用模型。記憶例外：每一輪有它自己的事實，不能互相取代。
        """
        if not handles:
            return
        kind_of = {
            event.task_id: event.kind
            for event in self._background.events()
            if event.action == "scheduled" and event.task_id
        }
        for handle in handles:
            kind = kind_of.get(handle.task_id)
            if kind is None:
                continue
            live = self._live_by_kind.setdefault(kind, [])
            live[:] = [item for item in live if not item.status.terminal]
            if kind is not BackgroundCognitionKind.MEMORY_EXTRACTION:
                for older in live:
                    older.cancel()
                live.clear()
            live.append(handle)

    def _superseded(self, proposal) -> bool:
        """這一筆之後，同一種工作有沒有排過更新的。

        引擎對情緒、摘要這類目標是「每個版本只收一筆」。舊的結果改掛到目前的版本
        會佔掉那個位子，真正屬於這個版本的觀察回來時反而被判成衝突丟掉——實測
        8 輪對話裡發生了兩次。所以有更新的要來，舊的就讓路。
        """
        if proposal.target == MEMORY_TARGET:
            return False
        every = self._every_by_target.get(proposal.target, 0)
        if every <= 0:
            return False
        later = range(proposal.base_revision + 1, self._tasks.revision + 1)
        return any(revision % every == 0 for revision in later)

    async def _collect(self, handle) -> None:
        try:
            result = await handle.wait()
            conversation = self._history_by_task.pop(handle.task_id, None)
            if result.output is None:
                logger.debug(
                    f"[engine] {result.task_type} {result.status.value}: {result.error}"
                )
                return
            # 跟 observe_turn 用同一把鎖：提交期間對話範圍不可以被下一輪換掉。
            async with self._turn_lock:
                committed = [
                    await self._commit(proposal, conversation)
                    for proposal in result.output.proposals
                ]
                if any(
                    outcome.committed and outcome.target == "state.emotion_candidate"
                    for outcome in committed
                ):
                    async with self._tasks.authority_guard():
                        patch = _relationship_patch(
                            self.runtime.state.snapshot(), count_turn=False
                        )
                        if patch is not None:
                            self.runtime.state.apply(patch)
                if any(outcome.committed for outcome in committed):
                    self._save_state()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                f"[engine] background result dropped ({type(exc).__name__}: {exc})"
            )
        finally:
            self._history_by_task.pop(handle.task_id, None)

    async def _commit(self, proposal, conversation: Optional[str]):
        """必須在 _turn_lock 裡呼叫。

        引擎寫記憶時用的是「提交當下」的對話範圍。背景結果晚到、而使用者已經切到
        另一段對話的話，記憶會落在新的那一段。所以提交期間把範圍換回這個工作
        當初所屬的對話。
        """
        current_scope = self.runtime.memory_scope_id
        if proposal.target in CONVERSATION_SCOPED_TARGETS:
            self.runtime.memory_scope_id = self._scope(conversation)
        try:
            outcome = await self._commits.commit(proposal)
            behind = self._tasks.revision - proposal.base_revision
            if (
                outcome.status is CommitStatus.STALE
                and outcome.reason == "foreground_revision_changed"
                and 0 < behind <= self.settings.max_rebase_turns
                and not self._superseded(proposal)
            ):
                rebased = self._commits.rebase(
                    proposal,
                    reason=f"observation is {behind} turn(s) old and still valid evidence",
                )
                outcome = await self._commits.commit(rebased)
        finally:
            self.runtime.memory_scope_id = current_scope
        if not outcome.committed:
            logger.debug(
                f"[engine] {proposal.target} {outcome.status.value}: "
                f"{outcome.reason} {dict(outcome.metadata) or ''}"
            )
        return outcome

    async def settle(self) -> None:
        """等目前在跑的背景工作與提交做完。對話不需要呼叫；給關閉流程與測試用。"""
        while self._pending:
            await asyncio.gather(*tuple(self._pending), return_exceptions=True)

    def flush(self) -> None:
        """把狀態存檔，工作階段照常運作。"""
        self._save_state()

    def retire(self) -> None:
        """被新的工作階段取代時呼叫（設定變了）。存最後一次檔，之後不再寫任何東西。

        每次儲存設定都會重建 agent，而舊的 agent 還被別的連線拿著。舊的工作階段
        繼續存檔的話，會把新的那一個累積的狀態蓋掉。
        """
        if self._retired:
            return
        self._save_state()
        self._retired = True
        self._closed = True
        for task in tuple(self._pending):
            task.cancel()
        try:
            closing = asyncio.get_running_loop().create_task(self._tasks.close())
        except RuntimeError:
            return
        self._pending.add(closing)
        closing.add_done_callback(self._pending.discard)

    async def close(self) -> None:
        """整個行程要結束時才呼叫；之後這個工作階段不再收任何一輪。"""
        if self._closed:
            return
        self._closed = True
        for task in tuple(self._pending):
            task.cancel()
        await asyncio.gather(*tuple(self._pending), return_exceptions=True)
        await self._tasks.close()
        self._save_state()

    # --- 讀取 ---------------------------------------------------------------

    def snapshot(self) -> CharacterSnapshot:
        state = self.runtime.state
        newest_first = sorted(
            self.runtime.long_term_cognition.reflections(
                character_id=self._character_id
            ),
            key=lambda record: record.created_at,
            reverse=True,
        )
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.settings.goal_max_age_days
        )
        goals = [
            goal.objective
            for goal in self.runtime.goal_manager.active_goals(
                character_id=self._character_id
            )
            if goal.updated_at >= cutoff
        ]
        return CharacterSnapshot(
            emotion=state.emotion,
            trust=state.trust,
            favorability=state.favorability,
            relationship_stage=state.relationship_stage,
            goals=tuple(goals),
            thoughts=tuple(record.insight for record in newest_first),
        )

    def memories(self, history_uid: Optional[str] = None) -> list[str]:
        """一段對話在引擎裡的記憶。這一版不注入系統提示，只供比對與檢視。"""
        scope = self._scope(history_uid if history_uid is not None else self._bound)
        records = self.runtime.memory_manager.store.list_for_character(scope)
        return [record.summary for record in records if record.is_active]
