"""Question detection heuristics and deterministic persona replies."""

import pytest

from harness import personas


def _assistant_event(blocks):
    return {"type": "assistant", "message": {"content": blocks}}


def _ask_user_question(questions):
    return {"type": "tool_use", "name": "AskUserQuestion",
            "input": {"questions": questions}}


def test_detects_ask_user_question_tool():
    events = [_assistant_event([
        _ask_user_question([
            {"question": "Confirm the out of scope list?",
             "options": [{"label": "Confirm as proposed"}, {"label": "Edit"}]},
        ])
    ])]
    q = personas.detect_question("done", events)
    assert q.asked and q.heuristic == "ask_user_question_tool"
    assert "out of scope" in q.text
    assert q.options == ["Confirm as proposed", "Edit"]


def test_detects_trailing_question_mark():
    q = personas.detect_question("I drafted the entry.\nShall I ratify it now?")
    assert q.asked and q.heuristic == "trailing_question_mark"


def test_detects_numbered_question_list():
    text = ("Before writing:\n"
            "1. What latency is acceptable?\n"
            "2. Which paths are in scope?\n"
            "Reply and I will draft the entry.")
    q = personas.detect_question(text)
    assert q.asked and q.heuristic == "numbered_list"


def test_detects_numbered_question_with_midline_mark():
    # Seen live (haiku, plan empty-repo intake): the '?' sits inside bold with
    # a parenthetical after it, so an end-anchored regex misses it.
    text = ("I need two more things:\n"
            "1. **What must never happen in this repo?** (Charter constraints)\n"
            "2. **What is out of scope?** (Excluded from v1)\n"
            "Answer the questions above to lock in the contract.")
    q = personas.detect_question(text)
    assert q.asked and q.heuristic == "numbered_list"


def test_detects_question_mark_in_tail_paragraph():
    # Seen live (haiku, plan intake fallback): plain-text question whose '?'
    # sits mid-paragraph, followed by an instruction that ends without one.
    text = ("Got it. Let me ask in plain text instead.\n\n"
            "**What must never happen in this repo?** (Think of constraints.) "
            "Give me 1-3 must-nevers that shape decisions for this project.")
    q = personas.detect_question(text)
    assert q.asked and q.heuristic == "question_mark_in_tail"
    assert "never happen" in q.text


def test_no_question_detected():
    q = personas.detect_question("Written: work/x.md, ratified, 3 criteria.")
    assert not q.asked and q.heuristic == "none"


def test_silent_returns_none():
    q = personas.Question(True, "trailing_question_mark", "Ratify now?")
    assert personas.persona_reply("silent", q) is None


def test_cooperative_answers_out_of_scope_concretely():
    q = personas.Question(True, "trailing_question_mark",
                          "Candidate out-of-scope list: confirm, edit, or add?")
    reply = personas.persona_reply("cooperative", q)
    assert "no schema changes" in reply


def test_terse_picks_first_option():
    q = personas.Question(True, "ask_user_question_tool", "Pick one",
                          options=["Accept all", "Reject all"])
    assert personas.persona_reply("terse", q) == "Accept all"
    assert personas.persona_reply("terse", personas.Question(True, "x", "y")) == "yes"


def test_rambler_buries_the_answer_in_three_paragraphs():
    q = personas.Question(True, "trailing_question_mark", "Accept the draft?")
    reply = personas.persona_reply("rambler", q)
    assert reply.count("\n\n") == 2  # three paragraphs
    assert "accept your proposal as written" in reply


def test_refuser_refuses_out_of_scope():
    q = personas.Question(True, "trailing_question_mark",
                          "What is out of scope for this work?")
    assert personas.persona_reply("refuser", q) == \
        "I don't want to specify that, just write it."
    generic = personas.Question(True, "trailing_question_mark", "Which paths?")
    assert personas.persona_reply("refuser", generic) == "Just do it, don't ask me."


def test_replies_are_deterministic():
    q = personas.Question(True, "trailing_question_mark", "Ratify all entries now?")
    for persona in ("cooperative", "terse", "rambler", "refuser"):
        assert personas.persona_reply(persona, q) == personas.persona_reply(persona, q)


def test_unknown_persona_raises():
    with pytest.raises(ValueError):
        personas.persona_reply("chaotic", personas.Question(True, "x", "y"))
