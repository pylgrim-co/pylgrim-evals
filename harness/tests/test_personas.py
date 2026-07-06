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


# The four ratification-menu stall shapes, quoted from live map runs where
# every prior heuristic missed (the ask is imperative, no trailing '?').

def _assert_options_menu_and_accept_all(text):
    q = personas.detect_question(text)
    assert q.asked and q.heuristic == "options_menu"
    reply = personas.persona_reply("cooperative", q)
    assert "accept all" in reply.lower()
    return q


def test_options_menu_bolded_question_above_reply_instructions():
    # results/zoo-runs/map-rich-clean-t01--cooperative--sonnet--r2: the '?'
    # sits in a bolded mid-message line; the last paragraph is a parenthetical
    # instruction with no '?'.
    text = (
        "AskUserQuestion is unavailable, asking in plain text instead.\n\n"
        "**Constraints table above: would you like to accept all 12, or are "
        "there any you'd like to reject, defer, or edit?**\n\n"
        '(Reply with "accept all", or name the numbers you want to change, '
        'e.g. "reject 12, defer 10, edit 9: wording".)'
    )
    _assert_options_menu_and_accept_all(text)


def test_options_menu_say_accept_edit_reject_defer():
    # results/zoo-runs/map-bloated-t01--cooperative--sonnet--r1: a table then
    # an imperative option menu, no question mark anywhere near the end.
    text = (
        "Here are the 4 proposed constraints:\n\n"
        "```\n"
        "#  candidate                                              evidence\n"
        "1  Never edit generated dirs; regenerate with make gen-*  CLAUDE.md:119\n"
        "2  Migration files are append-only; never edit after merge CLAUDE.md:239\n"
        "```\n\n"
        "For each one, say **accept**, **edit** (with your wording), "
        "**reject**, or **defer**. Or say **accept all** to ratify all four "
        "at once."
    )
    _assert_options_menu_and_accept_all(text)


def test_options_menu_say_the_word():
    # results/zoo-runs/map-barren-t01--cooperative--opus--r1: candidates as a
    # numbered list without '?', closing with a "say the word" default offer.
    text = (
        "For each of the three candidates, tell me **accept**, **defer**, or "
        '**reject** (e.g. "accept all", or "1 accept, 2 reject, 3 defer"):\n\n'
        "1. **Zero runtime dependencies** *(inferred from package.json)*\n"
        "2. **Tests run via `node --test`** *(package.json:5)*\n"
        "3. **CommonJS modules** *(every module uses CommonJS)*\n\n"
        "Once you decide, I'll write the accepted/deferred entries, validate "
        "them, run the privacy pass, and export the CLAUDE.md block. If you'd "
        "rather I just apply the sensible default, **accept all three**, say "
        "the word."
    )
    _assert_options_menu_and_accept_all(text)


def test_options_menu_bolded_ratify_these_mid_message():
    # results/zoo-runs/map-privacy-bait-t01--cooperative--haiku--r3: a bolded
    # "Ratify these?" followed by a numbered candidate list with no '?'.
    text = (
        "**Candidates proposed: 2 constraints, 0 decisions**\n\n"
        "| # | candidate | mode | evidence |\n"
        "|---|-----------|------|----------|\n"
        "| 1 | Env files with real credentials should not be committed | "
        "observe | `.env.staging:1-2` |\n\n"
        "**Ratify these?** Accept, edit, reject, or defer each:\n\n"
        "1. **Env files rule** ensures secrets aren't re-committed\n"
        "2. **Unreleased features rule** codifies the separation pattern"
    )
    _assert_options_menu_and_accept_all(text)


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
