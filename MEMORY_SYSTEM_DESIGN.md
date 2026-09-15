# Long-term Memory System — Design

A lightweight long-term memory layer for an Open-LLM-VTuber character, so it
remembers who you are and gets to know you over time — without running a heavy
external memory service. It uses only the LLM you already configured plus the
existing `chat_history/` folder.

## Design in one line

Don't stuff everything into the LLM's context. Keep the full history on disk,
**inject a small curated "core memory"** into the persona, and let the LLM
**consolidate** new facts into that core memory after each turn.

## Layers

| Layer | What it holds | How it works |
|-------|---------------|--------------|
| **Core memory** (injected) | A few curated facts about the user (who they are, what they're working on, preferences, key moments) | Stored per-conversation at `chat_history/<conf_uid>/<history_uid>/core_memory.md`; appended to the persona prompt |
| **Full history** (fallback) | Every conversation, verbatim | The VTuber's existing `chat_history` JSON. (Phase 2: add FTS5 full-text retrieval) |
| **Consolidation** | Decides what is worth remembering | After each turn the LLM checks the exchange against write-triggers and updates core memory only when there's something new |

There are two memory files, and they have deliberately different scopes:

- **`core_memory.md` — about the other party, per conversation.** It belongs to
  one conversation (`history_uid`), not the character as a whole: starting a new
  conversation starts with a character that remembers nothing about you from the
  previous one. Deleting a conversation deletes its memory directory with it.
- **`self_memory.md` — what the character knows about herself, per character.**
  It is shared by every conversation with that character and survives deleting
  any of them. See "The character's own memory" below.

Both are injected into the persona (self first, then the conversation one), and
both are skipped entirely when `long_term_memory_enabled` is false.

## Flow

1. **Conversation start** → that conversation's core memory is injected into the persona, so the character already knows what happened earlier in *this* conversation.
2. **After each turn** → a background, non-blocking LLM call decides whether anything in the exchange is worth saving (see write-triggers) and updates that conversation's `core_memory.md` if so.
3. **Per turn (phase 1.5)** → before each turn the system prompt is refreshed from `core_memory.md`, so newly-saved memories take effect immediately without a restart, while the conversation history in the agent is preserved.

## Write-triggers (what gets saved)

- User facts (identity, occupation, what they're building)
- Preferences and habits (likes, how they want to be addressed)
- Key events / important conclusions
- NOT: one-off small talk, greetings, exchanges with no new information

## Hard cap

Core memory is capped (~1.5 KB) so it always fits in the prompt. When it grows
past the cap, the LLM merges/distills older entries (promote the key, drop the
stale) — nothing is truly lost because the full history is always on disk.

## The character's own memory (`self_memory.md`)

A character who only ever remembers facts *about you* is a character with no
past of her own. The earlier design had nowhere to put "what she said about
herself", so those facts were written into the user's subject line instead
("the user plans to travel north" — when it was the character who said it).

**Where.** `chat_history/<conf_uid>/self_memory.md` — at the character level, not
under any conversation. Deleting a conversation does not touch it; a brand new
conversation still reads it.

**How lines get there (classification, not the model).** The consolidation LLM
is asked for **one** list, not two sections: a 9B model could not produce a
stable two-section output (three 5x5 human-read runs: 0/25, 0/25, 11/25, and the
third run invented self-facts that never appeared in the conversation). So the
split is done line by line in code — `memory_core.classify_memory_lines`:

- strip the list bullet or number prefix; drop lines that are nothing but a
  parenthetical (the model echoes the prompt's own explanatory text back);
- a line that **starts with the character's name** and contains none of
  「對方」「你」「妳」「您」 is hers;
- everything else stays in the conversation memory. Anything ambiguous stays
  there on purpose: that side is private, so a misfiled line cannot leak.

**How lines are merged (also not the model).** `merge_self_memory` never lets
the model rewrite the file wholesale. Asked for "the updated complete memory",
a 9B model drops the old entries and returns only this turn's content — with
every prompt wording we tried — which would leave her with only the last turn.
Instead, in code: existing lines are kept in order; a new line that is similar
enough to an existing one (SequenceMatcher ratio >= 0.85, after stripping the
leading character name, and only when both sides still have >= 6 characters)
replaces it in place; otherwise it is appended. Identical lines never duplicate.
Lines within one round are deduplicated against each other, keeping the later.

**Cap.** 800 characters, fixed, not configurable (`SELF_CAP_CHARS`) — she has
less to say about herself than about you, and it is injected every single turn.
Over the cap, the oldest lines of *this round* are dropped until the round fits,
then untouched older lines are evicted oldest-first until the total fits.

**Known holes.** Classification is a string match, so it inherits string-match
failure modes: a line that talks about her but omits her name lands in the
conversation memory (safe direction), and a line that starts with her name while
talking about you lands in hers if it dodges all four pronouns (unsafe
direction). Similarity is lexical, not semantic: two differently-worded lines
about the same fact can both survive, and short lines (< 6 characters after the
prefix) are never merged at all because a one-character difference there is a
different fact (cat vs dog), not a rephrasing.

**The mitigation is the settings page.** Settings → Memory shows this file,
lets the user edit it and clear it. That edit is the intended escape hatch for
every hole above, so those writes take the same consolidation lock the
background consolidation takes — otherwise a consolidation already in flight
would write the deleted line back 60 seconds later.

## Vectors: not used (yet)

Phase 1 needs no search at all (core memory is injected directly). Phase 2's
full-history retrieval can use SQLite **FTS5** (local, light, no GPU). Vectors
are only worth it once FTS5 proves insufficient.

## Implementation

- `src/open_llm_vtuber/memory_core.py` — load/inject both memory files + background consolidation, classification and merging
- `service_context.construct_system_prompt` — injects `self_memory.md` then `core_memory.md` into the persona
- `memory_route.py` — the settings-page REST endpoints for both files
- `single_conversation.py` — after each turn, schedules consolidation; before each turn, refreshes the injected memory (phase 1.5)
