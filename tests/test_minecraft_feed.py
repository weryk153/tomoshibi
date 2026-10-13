"""事件怎麼排隊、節流、合併成一輪；閒下來什麼時候算。"""

from src.open_llm_vtuber.minecraft.events import GameEvent, GameState
from src.open_llm_vtuber.minecraft.feed import IDLE_NOTE, FeedRules, GameFeed

RULES = FeedRules(idle_seconds=15, idle_cooldown=60, event_cooldown=30)
IDLE = GameState(is_idle=True, action="Idle")
BUSY = GameState(is_idle=False, action="collectBlocks")


def test_events_merge_into_one_turn_with_state_summary():
    feed = GameFeed(RULES)
    feed.observe(GameState(health=9), 0)
    assert feed.offer(GameEvent("found_item", "拿到鑽石"), 1)
    assert feed.offer(GameEvent("night", "天黑了"), 2)
    turn = feed.pick(3)
    assert turn is not None and turn.kind == "event" and not turn.urgent
    assert "拿到鑽石" in turn.notes[0] and "天黑了" in turn.notes[0]
    assert "9/20" in turn.notes[1]
    assert feed.pick(4) is None


def test_same_kind_is_throttled_but_death_is_not():
    feed = GameFeed(RULES)
    assert feed.offer(GameEvent("hostile", "殭屍"), 0)
    assert not feed.offer(GameEvent("hostile", "骷髏"), 10)
    assert feed.offer(GameEvent("hostile", "苦力怕"), 31)
    assert feed.offer(GameEvent("death", "死了", urgent=True), 32)
    assert feed.offer(GameEvent("death", "又死了", urgent=True), 33)


def test_urgent_only_returns_nothing_unless_a_death_is_waiting():
    feed = GameFeed(RULES)
    feed.offer(GameEvent("night", "天黑了"), 0)
    assert feed.pick(1, urgent_only=True) is None
    feed.offer(GameEvent("death", "死了", urgent=True), 2)
    turn = feed.pick(3, urgent_only=True)
    assert turn is not None and turn.urgent
    assert "天黑了" in turn.notes[0] and "死了" in turn.notes[0]
    assert feed.pending() == 0


def test_idle_turn_after_idle_seconds_then_cooldown():
    feed = GameFeed(RULES)
    for t in range(0, 14):
        feed.observe(IDLE, t)
        assert feed.pick(t) is None
    feed.observe(IDLE, 15)
    turn = feed.pick(15)
    assert turn is not None and turn.kind == "idle"
    assert turn.notes[-1] == IDLE_NOTE
    for t in range(16, 75):
        feed.observe(IDLE, t)
        assert feed.pick(t) is None
    feed.observe(IDLE, 75)
    assert feed.pick(75) is not None


def test_busy_resets_idle_clock():
    feed = GameFeed(RULES)
    feed.observe(IDLE, 0)
    feed.observe(BUSY, 10)
    feed.observe(IDLE, 11)
    feed.observe(IDLE, 25)
    assert feed.pick(25) is None
    feed.observe(IDLE, 26)
    assert feed.pick(26) is not None


def test_events_come_before_idle():
    feed = GameFeed(RULES)
    for t in range(0, 16):
        feed.observe(IDLE, t)
    feed.offer(GameEvent("night", "天黑了"), 16)
    assert feed.pick(16).kind == "event"
    assert feed.pick(17).kind == "idle"


def test_rules_can_be_swapped_while_running():
    feed = GameFeed(RULES)
    feed.rules = FeedRules(idle_seconds=3, idle_cooldown=0, event_cooldown=0)
    feed.observe(IDLE, 0)
    feed.observe(IDLE, 3)
    assert feed.pick(3) is not None
    feed.observe(IDLE, 4)
    assert feed.pick(4) is not None


def test_reset_idle_waits_for_a_fresh_idle_period():
    feed = GameFeed(RULES)
    feed.observe(IDLE, 0)
    feed.reset_idle()
    assert feed.latest is IDLE
    assert feed.pick(100) is None
    feed.observe(IDLE, 100)
    assert feed.pick(110) is None
    turn = feed.pick(115)
    assert turn is not None and turn.kind == "idle"


def test_not_ready_blocks_idle_turns_but_not_events_and_resumes():
    feed = GameFeed(RULES)
    ready = {"on": False}
    feed.ready = lambda: ready["on"]
    feed.observe(IDLE, 0)
    assert feed.pick(100) is None
    feed.offer(GameEvent("night", "天黑了"), 101)
    turn = feed.pick(102)
    assert turn is not None and turn.kind == "event"
    ready["on"] = True
    assert feed.pick(103).kind == "idle"
