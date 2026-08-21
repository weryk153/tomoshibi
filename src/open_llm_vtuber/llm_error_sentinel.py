"""Recognise the placeholder text an LLM backend yields when a call fails.

When a chat completion raises, the stateless LLM layers do not propagate the
exception — they ``yield`` an English sentence describing it, so the pipeline
keeps running and the user sees something instead of a dead session. That is a
reasonable choice for *display*, but the sentence then travels the whole path
like ordinary speech: it is spoken by TTS, written into chat history as a turn
by the character, and fed back as conversation context on later turns.

Real cost, measured on this machine: 75 of 231 stored assistant turns across 9
conversation files were this sentence. A model reading that history sees its own
past turns as English error text and has to make sense of it.

Kept as its own module so the check can be applied wherever a response is about
to be persisted or remembered, without those call sites importing each other.
"""

# The literal strings the LLM layers yield on failure. Matching a prefix rather
# than the whole sentence: the connection-error variant appends the endpoint,
# the exception cause and a docs URL, none of which are stable.
_ERROR_PREFIXES = (
    "Error calling the chat endpoint:",
    "Error: Failed to generate response",
)


def is_llm_error_placeholder(text: str) -> bool:
    """Whether this text is a backend failure notice rather than character speech."""
    stripped = str(text or "").strip()
    return any(stripped.startswith(prefix) for prefix in _ERROR_PREFIXES)
