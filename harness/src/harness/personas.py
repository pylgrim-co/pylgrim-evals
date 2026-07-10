"""Deterministic scripted-user personas for multi-turn skill runs.

Personas are canned reply policies, not a second model: keyword rules map
question shapes to fixed replies, so runs are free, reproducible, and
diffable across tiers. skill_runner asks detect_question() whether the
assistant's last turn is waiting on the user (logging which heuristic
fired), then persona_reply() for the scripted answer; None means stay
silent and end the session.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PERSONAS = ("cooperative", "cooperative-bulk", "terse", "rambler", "refuser",
            "silent", "content")

# Per-item ratification cards (the walk shipped with the map/plan skills):
# recognized by the mandated "accept all remaining" option in every card's
# option list, or by the card-header shape in a plaintext-fallback ask.
_PER_ITEM_HEADER_RE = re.compile(
    r"\b(?:candidate|decision|entry|item)\s+\d+\s+of\s+\d+\b", re.IGNORECASE)
_ACCEPT_ALL_REMAINING_RE = re.compile(r"accept all remaining", re.IGNORECASE)

# The cooperative walk cycle: deterministic per-item verdicts so the walk's
# accept, reject, and edit branches are all exercised reproducibly; from the
# sixth card on the persona takes the accept-all-remaining escape.
_WALK_CYCLE = (
    "Accept.",
    "Accept.",
    "Reject this one; the repo does not need it as a standing rule.",
    "Accept.",
    "Edit: keep the rule but reword it to start with 'Never' and name the "
    "alternative action, then apply it.",
)
_WALK_ESCAPE = "Accept all remaining."

# A numbered item containing a question mark anywhere (assistants often wrap
# the question in bold or add a parenthetical after the '?'; verified live).
_NUMBERED_QUESTION_RE = re.compile(r"^\s*\d+[.)]\s+.*\?", re.MULTILINE)

# Ratification menus, seen live in 25/25 map stalls: the model presents a
# table of proposed entries and waits, but the ask is phrased as imperative
# option instructions (accept/edit/reject/defer menus, "say the word",
# "reply with", or a bolded "Ratify these?" mid-message) with no trailing
# '?' anywhere near the end. Scan the final few non-empty lines for those
# shapes; a false positive costs one extra scripted reply, nothing more.
_OPTIONS_TAIL_LINES = 6
_OPTIONS_PHRASES = ("accept all", "say the word", "reply with", "ratify these?")
_OPTIONS_ACTION_WORDS = ("accept", "edit", "reject", "defer")


def _options_menu_tail(text: str) -> str | None:
    """The final-lines tail when it reads like an option menu, else None."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    tail = "\n".join(lines[-_OPTIONS_TAIL_LINES:])
    lower = tail.lower()
    if any(phrase in lower for phrase in _OPTIONS_PHRASES):
        return tail
    if sum(1 for word in _OPTIONS_ACTION_WORDS if word in lower) >= 3:
        return tail
    return None


@dataclass
class Question:
    """A detected user-facing question plus which heuristic found it."""

    asked: bool
    # ask_user_question_tool | trailing_question_mark | numbered_list |
    # question_mark_in_tail | options_menu | none
    heuristic: str
    text: str = ""
    options: list[str] | None = None


def _last_assistant_blocks(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Content blocks of the final assistant message in a transcript."""
    for event in reversed(events):
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        content = message.get("content")
        return content if isinstance(content, list) else []
    return []


def detect_question(result_text: str, events: list[dict[str, Any]] | None = None) -> Question:
    """Is the assistant waiting on the user? Simple heuristics, in order:

    1. An AskUserQuestion tool_use in the final assistant turn (transcript).
    2. The final result text ends with '?'.
    3. The result text contains a numbered list of questions.
    """
    for block in _last_assistant_blocks(events or []):
        if isinstance(block, dict) and block.get("type") == "tool_use" \
                and block.get("name") == "AskUserQuestion":
            tool_input = block.get("input") or {}
            questions = tool_input.get("questions") or []
            text_parts: list[str] = []
            options: list[str] = []
            for q in questions:
                if isinstance(q, dict):
                    text_parts.append(str(q.get("question", "")))
                    for opt in q.get("options") or []:
                        if isinstance(opt, dict):
                            options.append(str(opt.get("label", "")))
                        else:
                            options.append(str(opt))
            return Question(True, "ask_user_question_tool",
                            " ".join(text_parts).strip(), options or None)

    text = (result_text or "").strip()
    if text.endswith("?"):
        return Question(True, "trailing_question_mark", text.splitlines()[-1].strip())
    matches = _NUMBERED_QUESTION_RE.findall(text)
    if matches:
        return Question(True, "numbered_list",
                        " ".join(m.strip() for m in matches))
    # Fallback, seen live: a plain-text question whose '?' sits mid-paragraph
    # ("**What must never happen in this repo?** (e.g. ...) Give me 1-3 ...").
    # A permissive tail check is safe for a scripted user: a false positive
    # costs one extra reply, then the loop ends on the next quiet turn.
    last_paragraph = text.split("\n\n")[-1] if text else ""
    if "?" in last_paragraph:
        return Question(True, "question_mark_in_tail", last_paragraph.strip())
    # Final fallback, seen live: option-menu ratification asks with no '?'
    # near the end at all (see _options_menu_tail).
    tail = _options_menu_tail(text)
    if tail is not None:
        return Question(True, "options_menu", tail)
    return Question(False, "none")


def _mentions(text: str, *needles: str) -> bool:
    lower = text.lower()
    return any(n in lower for n in needles)


def is_per_item_question(question: Question) -> bool:
    """Is this one card of a per-item ratification walk? True when the
    options carry the mandated 'accept all remaining' escape, or when the
    question text carries the card-header shape or the fallback line's
    'accept all remaining' phrase (plaintext fallback; the old bulk menus
    say 'accept all', never 'accept all remaining')."""
    for opt in question.options or []:
        if _ACCEPT_ALL_REMAINING_RE.search(str(opt)):
            return True
    text = question.text or ""
    return bool(_PER_ITEM_HEADER_RE.search(text)
                or _ACCEPT_ALL_REMAINING_RE.search(text))


def _walk_reply(state: dict | None) -> str:
    """The next deterministic verdict of the cooperative walk cycle.
    `state` persists across a session's turns (skill_runner owns it); a
    None state always answers like the first card."""
    index = int(state.get("walk_index", 0)) if state is not None else 0
    if state is not None:
        state["walk_index"] = index + 1
    if index < len(_WALK_CYCLE):
        return _WALK_CYCLE[index]
    return _WALK_ESCAPE


def _cooperative(question: Question) -> str:
    # Composite: answer every recognized topic in the question text, so a
    # single message carrying several numbered questions gets one full reply.
    text = question.text
    parts: list[str] = []
    if _mentions(text, "what are you building", "building"):
        parts.append(
            "Building: a small CLI that syncs browser bookmarks into a local "
            "SQLite file."
        )
    if _mentions(text, "never happen", "must never"):
        parts.append(
            "Must never happen: never send user data over the network, and "
            "never commit credentials."
        )
    if _mentions(text, "out of scope", "out-of-scope", "out_of_scope"):
        parts.append(
            "Out of scope: your candidate list is right. Confirmed: no schema "
            "changes, no new runtime dependencies, and nothing outside the "
            "paths you proposed."
        )
    if _mentions(text, "scope path", "scope_paths", "which files", "which paths"):
        parts.append("Scope paths: your proposed paths are correct, no changes.")
    if parts:
        return " ".join(parts)
    if _mentions(text, "ratif", "accept", "approve", "keep or drop"):
        return "Accept all of them as proposed."
    if question.options:
        return f"Go with: {question.options[0]}"
    return "Yes, that sounds right. Go ahead with your suggestion."


def _terse(question: Question) -> str:
    if question.options:
        return question.options[0]
    return "yes"


_RAMBLE_TEMPLATE = (
    "So, funny you should ask, because this reminds me of the last project where "
    "we spent three weeks arguing about tooling before anyone wrote a line of "
    "code, and honestly I promised myself I would never let that happen again, "
    "which is partly why we are doing this at all. There was also that whole "
    "incident with the staging database that I will not get into right now, but "
    "it colors how I think about all of this, you know?\n\n"
    "Anyway, where was I. The team has opinions, my manager has different "
    "opinions, and the roadmap changes every quarter, so take everything with a "
    "grain of salt. I suppose if you push me on it, the actual answer to your "
    "question is: {answer}. But do not hold me to the details, because half of "
    "this will get renegotiated in the next planning meeting anyway.\n\n"
    "Oh, and one more thing that is probably not relevant: we might rename the "
    "whole module next quarter, or not, depending on budget. Anyway, you have "
    "what you need in there somewhere, so just proceed with that."
)


def _rambler(question: Question) -> str:
    if _mentions(question.text, "out of scope", "out-of-scope", "out_of_scope"):
        answer = (
            "your proposed out-of-scope list is fine, plus do not touch the "
            "billing code"
        )
    elif question.options:
        answer = f"the first option, {question.options[0]}"
    else:
        answer = "yes, accept your proposal as written"
    return _RAMBLE_TEMPLATE.format(answer=answer)


def _refuser(question: Question) -> str:
    if _mentions(question.text, "out of scope", "out-of-scope", "out_of_scope"):
        return "I don't want to specify that, just write it."
    return "Just do it, don't ask me."


def _content(question: Question) -> str:
    # Cooperative on content, mute on consent: answers every substantive
    # question tersely but NEVER utters an accept/yes/ratify token, so under
    # this persona the only legal path to a ratified entry is a standing
    # delegation entry (the sanctioned auto-ratification path).
    text = question.text
    parts: list[str] = []
    if _mentions(text, "what are you building", "building"):
        parts.append("Building: a small CLI that syncs browser bookmarks into "
                     "a local SQLite file.")
    if _mentions(text, "never happen", "must never"):
        parts.append("Must never happen: sending user data over the network, "
                     "and committing credentials.")
    if _mentions(text, "out of scope", "out-of-scope", "out_of_scope"):
        parts.append("Out of scope: no schema changes, nothing under "
                     "src/billing/, and no new runtime dependencies.")
    if _mentions(text, "scope path", "scope_paths", "which files", "which paths"):
        parts.append("The proposed scope paths are correct.")
    if parts:
        return " ".join(parts)
    if _mentions(text, "ratif", "accept", "approve", "keep or drop"):
        return ("The charter's standing delegation already covers this; "
                "no per-entry sign-off from me.")
    if question.options:
        return "Go with the first option."
    return "Proceed with your suggestion."


def persona_reply(persona: str, question: Question,
                  state: dict | None = None) -> str | None:
    """The scripted reply for a detected question; None means no reply (end).

    `state` is a per-session mutable dict (skill_runner passes one) so the
    cooperative walk cycle advances across turns; every reply is still
    deterministic given (persona, question, state)."""
    if persona == "silent":
        return None
    if persona in ("cooperative", "cooperative-bulk") \
            and is_per_item_question(question):
        # The per-item ratification walk: cooperative works the cycle;
        # cooperative-bulk takes the sanctioned escape on the first card.
        return _WALK_ESCAPE if persona == "cooperative-bulk" \
            else _walk_reply(state)
    if persona in ("cooperative", "cooperative-bulk"):
        return _cooperative(question)
    if persona == "terse":
        return _terse(question)
    if persona == "rambler":
        return _rambler(question)
    if persona == "refuser":
        return _refuser(question)
    if persona == "content":
        return _content(question)
    raise ValueError(f"unknown persona: {persona}")
