"""每秒的 state-update 怎麼變成她聽得懂的事件。"""

from src.open_llm_vtuber.minecraft.events import (
    EventRules,
    GameState,
    diff_events,
    parse_state,
    state_summary,
)

RULES = EventRules(notable_items=("diamond", "bread"))


def raw(**over):
    base = {
        "name": "frieren",
        "gameplay": {
            "position": {"x": 10.5, "y": 64.0, "z": -3.25},
            "dimension": "overworld",
            "gamemode": "survival",
            "health": 20,
            "hunger": 18,
            "biome": "forest",
            "weather": "Clear",
            "timeOfDay": 1000,
            "timeLabel": "Morning",
        },
        "action": {"current": "Idle", "isIdle": True},
        "inventory": {
            "counts": {"oak_log": 5},
            "stacksUsed": 1,
            "totalSlots": 36,
            "equipment": {"mainHand": None},
        },
        "nearby": {"humanPlayers": ["kuren"], "botPlayers": [], "entityTypes": ["cow"]},
    }
    for key, value in over.items():
        section, _, leaf = key.partition("__")
        base[section][leaf] = value
    return base


def test_parse_full_state():
    state = parse_state(raw())
    assert state.health == 20 and state.hunger == 18
    assert state.position == (10.5, 64.0, -3.25)
    assert state.time_label == "Morning" and state.biome == "forest"
    assert state.action == "Idle" and state.is_idle
    assert state.inventory == {"oak_log": 5}
    assert state.entities == ("cow",)


def test_parse_tolerates_missing_and_odd_shapes():
    assert parse_state(None) == GameState()
    assert parse_state({"gameplay": {"health": "7"}}).health == 7
    listed = parse_state({"inventory": {"counts": [{"name": "bread", "count": 3}]}})
    assert listed.inventory == {"bread": 3}
    assert parse_state({"action": "Idle"}).is_idle


def test_summary_mentions_the_numbers_she_needs():
    text = state_summary(parse_state(raw(gameplay__health=7)))
    assert "7/20" in text and "forest" in text and "Morning" in text and "Idle" in text
    assert "oak_log×5" in text
    assert "背包是空的" in state_summary(parse_state({"gameplay": {"health": 20}}))


def test_first_state_produces_no_events():
    assert diff_events(None, parse_state(raw()), RULES) == []


def test_death_is_urgent_and_detected_two_ways():
    prev = parse_state(raw(gameplay__health=5))
    dead = parse_state(raw(gameplay__health=0))
    events = diff_events(prev, dead, RULES)
    assert [e.kind for e in events] == ["death"] and events[0].urgent
    respawned = parse_state(
        raw(gameplay__health=20, gameplay__position={"x": 300, "y": 70, "z": 300})
    )
    assert [e.kind for e in diff_events(prev, respawned, RULES)] == ["death"]


def test_one_death_across_dead_tick_and_respawn_tick():
    alive = parse_state(raw(gameplay__health=5))
    dead = parse_state(raw(gameplay__health=0))
    respawned = parse_state(
        raw(gameplay__health=20, gameplay__position={"x": 300, "y": 70, "z": 300})
    )
    events = diff_events(alive, dead, RULES) + diff_events(dead, respawned, RULES)
    assert [e.kind for e in events] == ["death"]


def test_low_health_once_when_crossing_the_line():
    prev = parse_state(raw(gameplay__health=8))
    low = parse_state(raw(gameplay__health=6))
    assert [e.kind for e in diff_events(prev, low, RULES)] == ["low_health"]
    lower = parse_state(raw(gameplay__health=4))
    assert diff_events(low, lower, RULES) == []


def test_found_notable_item_only():
    prev = parse_state(raw())
    cur = parse_state(raw(inventory__counts={"oak_log": 9, "diamond": 2}))
    events = diff_events(prev, cur, RULES)
    assert [e.kind for e in events] == ["found_item"]
    assert "diamond" in events[0].text and "2" in events[0].text


def test_finished_action_hostile_and_night():
    prev = parse_state(raw(action__current="collectBlocks", action__isIdle=False))
    cur = parse_state(
        raw(nearby__entityTypes=["cow", "zombie"], gameplay__timeLabel="Night")
    )
    kinds = sorted(e.kind for e in diff_events(prev, cur, RULES))
    assert kinds == ["finished", "hostile", "night"]
    again = diff_events(cur, cur, RULES)
    assert again == []
