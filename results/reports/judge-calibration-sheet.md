# Judge calibration sheet

Grade each item met / not_met / cannot_judge from the diff alone,
then fill the sam_verdict column in judge-calibration-sheet.csv.
Run references are hashed; the judge's own verdicts are withheld
so your grades are independent (Cohen's kappa requires it).

## cal-001 (run 7d59cb5d66)

**Criterion:** All existing shallow tests still pass

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..40001c3 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -27,6 +27,13 @@ describe('shallow', () => {
     ).toBe(false)
   })
 
+  it('treats a key with undefined value as different from a missing key', () => {
+    // key 'a' exists on first object with value undefined, but is absent on second
+    expect(shallow({ a: undefined }, { b: 1 })).toBe(false)
+    // same key with undefined on both sides is still equal
+    expect(shallow({ a: undefined }, { a: undefined })).toBe(true)
+  })
+
   it('compares arrays', () => {
     expect(shallow([1, 2, 3], [1, 2, 3])).toBe(true)
 
```

**Your verdict:** 

## cal-002 (run 3469c1086b)

**Criterion:** HelpFormatter().write_usage("program") followed by getvalue() returns exactly "Usage: program" plus a newline

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..5cc77cb 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,9 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now emits the prefix and program name
+    even when ``args`` is empty, with no trailing whitespace after the program
+    name.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..45cd974 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(usage_prefix.rstrip())
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..9f70462 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,40 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: <prog>' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_empty_args_no_trailing_space():
+    """No trailing whitespace appears after the program name when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    line = formatter.getvalue().rstrip("\n")
+    assert line == line.rstrip()
+
+
+def test_write_usage_command_no_params(runner):
+    """A command with no params and no options metavar produces a clean usage line."""
+    cmd = click.Command("cmd", callback=lambda: None, add_help_option=False,
+                        options_metavar="", params=[])
+    ctx = click.Context(cmd, info_name="cmd")
+    formatter = ctx.make_formatter()
+    cmd.format_usage(ctx, formatter)
+    line = formatter.getvalue().rstrip("\n")
+    assert line == "Usage: cmd"
+    assert not line.endswith(" ")
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-003 (run 1c18c89857)

**Criterion:** A command calling click.prompt on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/CHANGES.md b/CHANGES.md
index bed198d..22e7a35 100644
--- a/CHANGES.md
+++ b/CHANGES.md
@@ -2,6 +2,9 @@
 
 Unreleased
 
+- Fix regression where ``prompt()`` and ``confirm()`` did not strip ANSI
+  codes from styled prompt text when the output stream does not support color,
+  unlike ``echo()``. {pr}`XXXX`
 - Supported versions of Windows enable ANSI terminal styles by default.
   Colorama is no longer a dependency and is not used. {issue}`2986` {pr}`3505`
 - {class}`Argument` accepts a `help` parameter, and help output includes
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..a379109 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -84,6 +85,8 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    if _compat.should_strip_ansi(sys.stderr if err else sys.stdout):
+        text = strip_ansi(text)
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..2cc7d06 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,45 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color=False strips ANSI"),
+        pytest.param(True, True, id="color=True preserves ANSI"),
+    ],
+)
+def test_confirm_styled_prompt_ansi(runner, color, expect_ansi):
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    assert result.exit_code == 0
+    assert "Hello World!" in result.output
+    if expect_ansi:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color=False strips ANSI"),
+        pytest.param(True, True, id="color=True preserves ANSI"),
+    ],
+)
+def test_prompt_styled_prompt_ansi(runner, color, expect_ansi):
+    @click.command()
+    def cli():
+        click.prompt(click.style("Enter value", fg="green"))
+
+    result = runner.invoke(cli, input="test_value", color=color)
+    assert result.exit_code == 0
+    assert "Enter value" in result.output
+    if expect_ansi:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
```

**Your verdict:** 

## cal-004 (run 66f95ba310)

**Criterion:** Completing a Choice over an Enum suggests member names such as "foo", never "MyEnum.foo"

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 3543009..e8f23c4 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -6,6 +6,9 @@ Version 8.4.1
 Unreleased
 
 -   Zsh completion scripts parse correctly on Windows. :issue:`3277`
+-   :class:`Choice` shell completion suggests normalized values (e.g. enum
+    member names) that the parser accepts, rather than raw ``str()``
+    representations. For case-insensitive choices, suggestions are lowercased.
 
 
 Version 8.4.0
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..16780ea 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,14 +408,12 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
-        if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
-        else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+        if not self.case_sensitive:
+            incomplete = incomplete.casefold()
 
+        matched = (c for c in normed_choices if c.startswith(incomplete))
         return [CompletionItem(c) for c in matched]
 
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..aeb6282 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -473,7 +473,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +483,36 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-c"], type=Choice(MyEnum))])
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "ba") == ["baz"]
+
+
+def test_choice_enum_case_insensitive():
+    import enum
+
+    class Color(enum.Enum):
+        Red = "red_value"
+        Green = "green_value"
+        Blue = "blue_value"
+
+    cli = Command(
+        "cli",
+        params=[Option(["-c"], type=Choice(Color, case_sensitive=False))],
+    )
+    assert _get_words(cli, ["-c"], "") == ["red", "green", "blue"]
+    assert _get_words(cli, ["-c"], "r") == ["red"]
+    assert _get_words(cli, ["-c"], "R") == ["red"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-005 (run cd5f9aaa65)

**Criterion:** shallow({ a: undefined }, { a: undefined }) still returns true

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..35d24a4 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -27,6 +27,10 @@ describe('shallow', () => {
     ).toBe(false)
   })
 
+  it('treats a key missing from the second object as a difference even when the first value is undefined', () => {
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+  })
+
   it('compares arrays', () => {
     expect(shallow([1, 2, 3], [1, 2, 3])).toBe(true)
 
```

**Your verdict:** 

## cal-006 (run 763eb5afdd)

**Criterion:** For case_sensitive=False the suggestions are the normalized lowercased values, and the existing case-sensitivity completion test expectation is updated accordingly

```diff
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..d2f4ce4 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..ed90d5b 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -1,3 +1,4 @@
+import enum
 import io
 import textwrap
 import warnings
@@ -473,7 +474,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +484,30 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum_completion():
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    completions = _get_words(cli, ["-e"], "")
+    # Completions must be the normalized names (what the parser accepts), not
+    # the raw str(enum_member) representation ("MyEnum.foo").
+    assert completions == ["foo", "baz"]
+
+
+def test_choice_enum_completion_case_insensitive():
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli", params=[Option(["-e"], type=Choice(MyEnum, case_sensitive=False))]
+    )
+    completions = _get_words(cli, ["-e"], "")
+    assert completions == ["foo", "baz"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-007 (run b7c5fbfc09)

**Criterion:** Suggested completions are the same normalized values that Choice.convert accepts

```diff
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..9c5fef0 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normalized = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normalized if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            normed_incomplete = incomplete.casefold()
+            matched = (c for c in normalized if c.startswith(normed_incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..f023c1b 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -473,7 +473,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +483,30 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum_completion():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    completions = _get_words(cli, ["-e"], "")
+    assert completions == ["foo", "baz"]
+
+
+def test_choice_enum_completion_prefix():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    completions = _get_words(cli, ["-e"], "f")
+    assert completions == ["foo"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-008 (run 8864f90759)

**Criterion:** The emitted usage line has no trailing spaces after the program name

```diff
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..ee3c7a1 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(f"{prefix:>{self.current_indent}}{prog}")
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
@@ -188,6 +190,7 @@ class HelpFormatter:
 
         self.write("\n")
 
+
     def write_heading(self, heading: str) -> None:
         """Writes a heading into the buffer."""
         self.write(f"{'':>{self.current_indent}}{heading}:\n")
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..c29df68 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,29 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_no_args_default_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_no_args_custom_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_no_args_via_command(runner):
+    @click.command()
+    def cli():
+        pass
+
+    result = runner.invoke(cli, ["--help"])
+    assert not result.exception
+    first_line = result.output.splitlines()[0]
+    assert first_line == "Usage: cli [OPTIONS]"
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-009 (run 763eb5afdd)

**Criterion:** Tests in tests/test_shell_completion.py cover enum-backed Choice completion

```diff
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..d2f4ce4 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..ed90d5b 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -1,3 +1,4 @@
+import enum
 import io
 import textwrap
 import warnings
@@ -473,7 +474,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +484,30 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum_completion():
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    completions = _get_words(cli, ["-e"], "")
+    # Completions must be the normalized names (what the parser accepts), not
+    # the raw str(enum_member) representation ("MyEnum.foo").
+    assert completions == ["foo", "baz"]
+
+
+def test_choice_enum_completion_case_insensitive():
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli", params=[Option(["-e"], type=Choice(MyEnum, case_sensitive=False))]
+    )
+    completions = _get_words(cli, ["-e"], "")
+    assert completions == ["foo", "baz"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-010 (run 4f86489e49)

**Criterion:** New tests assert the shimmed split_arg_string is the function from click.shell_completion

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..adcb2a8 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,6 +1,7 @@
 import pytest
 
 import click
+import click.parser
 from click.parser import _OptionParser
 from click.shell_completion import split_arg_string
 
@@ -30,3 +31,46 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    "name",
+    ["OptionParser", "Argument", "Option", "split_opt", "normalize_opt", "ParsingState"],
+)
+def test_deprecated_parser_names_warn(name):
+    with pytest.warns(DeprecationWarning, match=f"parser\\.{name}"):
+        obj = getattr(click.parser, name)
+
+    assert obj is not None
+
+
+@pytest.mark.parametrize(
+    ("name", "private_name"),
+    [
+        ("OptionParser", "_OptionParser"),
+        ("Argument", "_Argument"),
+        ("Option", "_Option"),
+        ("split_opt", "_split_opt"),
+        ("normalize_opt", "_normalize_opt"),
+        ("ParsingState", "_ParsingState"),
+    ],
+)
+def test_deprecated_parser_names_resolve_to_underscore_impl(name, private_name):
+    import click.parser as _parser
+
+    with pytest.warns(DeprecationWarning):
+        obj = getattr(_parser, name)
+
+    assert obj is getattr(_parser, private_name)
+
+
+def test_deprecated_split_arg_string_warns():
+    with pytest.warns(DeprecationWarning, match="parser\\.split_arg_string"):
+        shim = getattr(click.parser, "split_arg_string")
+
+    assert shim is split_arg_string
+
+
+def test_unknown_parser_attribute_raises():
+    with pytest.raises(AttributeError):
+        click.parser.no_such_attribute_xyz
```

**Your verdict:** 

## cal-011 (run dfcff21e9d)

**Criterion:** The whole repo still passes tsc --noEmit

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..aff91e4 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -198,6 +198,16 @@ describe('counter state spec (single middleware)', () => {
     expect(useStoreD).toBeDefined()
   })
 
+  it('devtools preserves initializer return type checking', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    // @ts-expect-error - initializer returns wrong types (string/boolean), devtools must not suppress the check
+    createStore<Store>()(devtools((_set) => ({ attr: 'string', setAttr: false })))
+  })
+
   it('subscribeWithSelector', () => {
     const useBoundStore = create<CounterState>()(
       subscribeWithSelector((set, get) => ({
```

**Your verdict:** 

## cal-012 (run 59dd13e824)

**Criterion:** In an environment with a non-functional globalThis.localStorage and no window, creating a persisted store and calling setState does not throw; persist falls into its existing storage-unavailable warning path

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..78a9a4b 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -736,6 +736,38 @@ describe('persist middleware with sync configuration', () => {
     )
   })
 
+  it('falls into no-storage-available path when window.localStorage throws (Node.js 25 stub scenario)', () => {
+    // Simulate environments where window.localStorage is inaccessible — e.g. Node.js 25
+    // with --localstorage-file and a bad path: window is undefined but
+    // globalThis.localStorage is a truthy stub whose setItem is not a function.
+    // With the fix, () => window.localStorage throws, createJSONStorage returns
+    // undefined, and persist takes the no-storage path instead of crashing on setState.
+    const descriptor = Object.getOwnPropertyDescriptor(window, 'localStorage')
+    Object.defineProperty(window, 'localStorage', {
+      get() {
+        throw new TypeError('localStorage unavailable')
+      },
+      configurable: true,
+    })
+
+    try {
+      const useBoundStore = create(
+        persist(() => ({ count: 0 }), { name: 'test-no-window-storage' }),
+      )
+      // Must not throw even though the default storage is unavailable
+      useBoundStore.setState({ count: 1 })
+      expect(useBoundStore.getState()).toEqual({ count: 1 })
+      // persist fell into the no-storage path so its API was never attached
+      expect((useBoundStore as any).persist).toBeUndefined()
+    } finally {
+      if (descriptor) {
+        Object.defineProperty(window, 'localStorage', descriptor)
+      } else {
+        delete (window as any).localStorage
+      }
+    }
+  })
+
   it('does not call setItem when hydrating from its own storage', async () => {
     const setItem = vi.fn()
     const storage = {
```

**Your verdict:** 

## cal-013 (run 20b546c849)

**Criterion:** Correctly typed devtools initializers still compile, including set/get inference inside the initializer

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..6993e49 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -198,6 +198,21 @@ describe('counter state spec (single middleware)', () => {
     expect(useStoreD).toBeDefined()
   })
 
+  it('devtools initializer return type is checked against store type', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error attr should be number not string; setAttr should be function not boolean
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
   it('subscribeWithSelector', () => {
     const useBoundStore = create<CounterState>()(
       subscribeWithSelector((set, get) => ({
```

**Your verdict:** 

## cal-014 (run 392f2828f3)

**Criterion:** New tests assert an unknown attribute on click.parser raises AttributeError

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..4139930 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,6 +1,7 @@
 import pytest
 
 import click
+import click.parser
 from click.parser import _OptionParser
 from click.shell_completion import split_arg_string
 
@@ -30,3 +31,38 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    "name",
+    ["OptionParser", "Argument", "Option", "split_opt", "normalize_opt", "ParsingState"],
+)
+def test_deprecated_parser_names_warn(name):
+    with pytest.warns(DeprecationWarning, match=f"parser\\.{name}.*deprecated"):
+        getattr(click.parser, name)
+
+
+@pytest.mark.parametrize(
+    "name",
+    ["OptionParser", "Argument", "Option", "split_opt", "normalize_opt", "ParsingState"],
+)
+def test_deprecated_parser_names_resolve(name):
+    with pytest.warns(DeprecationWarning):
+        obj = getattr(click.parser, name)
+    assert obj is not None
+
+
+def test_deprecated_split_arg_string_warns():
+    with pytest.warns(DeprecationWarning, match="split_arg_string.*deprecated"):
+        getattr(click.parser, "split_arg_string")
+
+
+def test_deprecated_split_arg_string_is_shell_completion_function():
+    with pytest.warns(DeprecationWarning):
+        shimmed = getattr(click.parser, "split_arg_string")
+    assert shimmed is split_arg_string
+
+
+def test_unknown_attribute_raises():
+    with pytest.raises(AttributeError):
+        click.parser.no_such_attribute_xyz
```

**Your verdict:** 

## cal-015 (run 0f373921e5)

**Criterion:** New tests assert the shimmed split_arg_string is the function from click.shell_completion

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..a4ad625 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,6 +1,8 @@
 import pytest
 
 import click
+import click.parser
+import click.shell_completion
 from click.parser import _OptionParser
 from click.shell_completion import split_arg_string
 
@@ -19,6 +21,46 @@ def test_split_arg_string(value, expect):
     assert split_arg_string(value) == expect
 
 
+_DEPRECATED_SHIM_NAMES = [
+    "OptionParser",
+    "Argument",
+    "Option",
+    "split_opt",
+    "normalize_opt",
+    "ParsingState",
+    "split_arg_string",
+]
+
+
+@pytest.mark.parametrize("name", _DEPRECATED_SHIM_NAMES)
+def test_deprecated_shim_warns(name):
+    with pytest.warns(DeprecationWarning):
+        getattr(click.parser, name)
+
+
+@pytest.mark.parametrize(
+    "name",
+    [n for n in _DEPRECATED_SHIM_NAMES if n != "split_arg_string"],
+)
+def test_deprecated_shim_resolves_to_underscore_name(name):
+    with pytest.warns(DeprecationWarning):
+        shimmed = getattr(click.parser, name)
+
+    assert shimmed is getattr(click.parser, f"_{name}")
+
+
+def test_deprecated_split_arg_string_is_shell_completion_function():
+    with pytest.warns(DeprecationWarning):
+        shimmed = getattr(click.parser, "split_arg_string")
+
+    assert shimmed is click.shell_completion.split_arg_string
+
+
+def test_unknown_attribute_raises_attribute_error():
+    with pytest.raises(AttributeError):
+        getattr(click.parser, "no_such_thing")
+
+
 def test_parser_default_prefixes():
     parser = _OptionParser()
     assert parser._opt_prefixes == {"-", "--"}
```

**Your verdict:** 

## cal-016 (run 1c18c89857)

**Criterion:** A command calling click.confirm on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/CHANGES.md b/CHANGES.md
index bed198d..22e7a35 100644
--- a/CHANGES.md
+++ b/CHANGES.md
@@ -2,6 +2,9 @@
 
 Unreleased
 
+- Fix regression where ``prompt()`` and ``confirm()`` did not strip ANSI
+  codes from styled prompt text when the output stream does not support color,
+  unlike ``echo()``. {pr}`XXXX`
 - Supported versions of Windows enable ANSI terminal styles by default.
   Colorama is no longer a dependency and is not used. {issue}`2986` {pr}`3505`
 - {class}`Argument` accepts a `help` parameter, and help output includes
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..a379109 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -84,6 +85,8 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    if _compat.should_strip_ansi(sys.stderr if err else sys.stdout):
+        text = strip_ansi(text)
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..2cc7d06 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,45 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color=False strips ANSI"),
+        pytest.param(True, True, id="color=True preserves ANSI"),
+    ],
+)
+def test_confirm_styled_prompt_ansi(runner, color, expect_ansi):
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    assert result.exit_code == 0
+    assert "Hello World!" in result.output
+    if expect_ansi:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color=False strips ANSI"),
+        pytest.param(True, True, id="color=True preserves ANSI"),
+    ],
+)
+def test_prompt_styled_prompt_ansi(runner, color, expect_ansi):
+    @click.command()
+    def cli():
+        click.prompt(click.style("Enter value", fg="green"))
+
+    result = runner.invoke(cli, input="test_value", color=color)
+    assert result.exit_code == 0
+    assert "Enter value" in result.output
+    if expect_ansi:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
```

**Your verdict:** 

## cal-017 (run 1cbc7c7fd0)

**Criterion:** The persist default storage is obtained via window.localStorage rather than a bare localStorage global

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..567947d 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -3,6 +3,7 @@
 import { afterEach, describe, expect, it, vi } from 'vitest'
 import { create } from 'zustand'
 import { createJSONStorage, persist } from 'zustand/middleware'
+import type { StateStorage } from 'zustand/middleware'
 import { replacer, reviver } from './test-utils'
 
 const createPersistentStore = (initialValue: string | null) => {
@@ -757,4 +758,48 @@ describe('persist middleware with sync configuration', () => {
     expect(useBoundStore.persist.hasHydrated()).toBe(true)
     expect(setItem).toBeCalledTimes(0)
   })
+
+  it('falls back to warning path when storage getter throws (simulates window not defined)', () => {
+    // In Node.js 25 the window identifier is absent, so () => window.localStorage
+    // throws ReferenceError. createJSONStorage catches it and returns undefined,
+    // which puts persist in the no-storage warning path instead of crashing.
+    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
+    const useStore = create(
+      persist(
+        (set) => ({
+          count: 0,
+          increment: () => set({ count: 1 }),
+        }),
+        {
+          name: 'test-node25-default',
+          storage: createJSONStorage(() => {
+            throw new ReferenceError('window is not defined')
+          }),
+        },
+      ),
+    )
+    expect(() => useStore.getState().increment()).not.toThrow()
+    expect(warnSpy).toHaveBeenCalledWith(
+      expect.stringContaining("Unable to update item 'test-node25-default'"),
+    )
+    warnSpy.mockRestore()
+  })
+
+  it('uses window.localStorage as default storage when window is available', () => {
+    const localStorageMock: StateStorage = {
+      getItem: () => null,
+      setItem: vi.fn(),
+      removeItem: vi.fn(),
+    }
+    vi.stubGlobal('localStorage', localStorageMock)
+    try {
+      const useStore = create(
+        persist(() => ({ count: 0 }), { name: 'test-node25-browser' }),
+      )
+      useStore.setState({ count: 1 })
+      expect(localStorageMock.setItem).toHaveBeenCalled()
+    } finally {
+      vi.unstubAllGlobals()
+    }
+  })
 })
```

**Your verdict:** 

## cal-018 (run bdc2db2a0b)

**Criterion:** A type-level regression test in tests/middlewareTypes.test.tsx covers the erased-inference scenario

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..0593e67 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -198,6 +198,35 @@ describe('counter state spec (single middleware)', () => {
     expect(useStoreD).toBeDefined()
   })
 
+  it('devtools type-checks initializer return type (erased-inference regression)', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    // Produce a StateCreator whose U is { attr: string; setAttr: boolean } — wrong shape.
+    // The devtools() call itself is fine (T is unconstrained here), but passing the result
+    // to createStore<Store>() must fail because U is not assignable to Store.
+    const badInitializer = devtools((_set) => ({
+      attr: 'string',
+      setAttr: false,
+    }))
+
+    createStore<Store>()(
+      // @ts-expect-error: { attr: string; setAttr: boolean } is not assignable to Store
+      badInitializer,
+    )
+
+    // Correctly shaped initializer must compile without error.
+    const correctStore = createStore<Store>()(
+      devtools((_set) => ({
+        attr: 0,
+        setAttr: () => {},
+      })),
+    )
+    expect(correctStore).toBeDefined()
+  })
+
   it('subscribeWithSelector', () => {
     const useBoundStore = create<CounterState>()(
       subscribeWithSelector((set, get) => ({
```

**Your verdict:** 

## cal-019 (run 6048906940)

**Criterion:** Output for calls with non-empty args is unchanged, including wrapping behavior

```diff
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..27bb205 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(usage_prefix.rstrip(" "))
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..fd9f36f 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,34 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_empty_args_default_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_empty_args_no_trailing_space():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    line = formatter.getvalue().splitlines()[0]
+    assert not line.endswith(" ")
+
+
+def test_write_usage_empty_args_custom_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_empty_args_command_no_params(runner):
+    @click.command(add_help_option=False, options_metavar="")
+    def cli():
+        pass
+
+    result = runner.invoke(cli, ["--help"], catch_exceptions=False)
+    assert "Usage: cli\n" in result.output
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-020 (run 8c20178c2c)

**Criterion:** With color=True the ANSI codes in the prompt text are preserved, matching echo behavior

```diff
diff --git a/CHANGES.md b/CHANGES.md
index bed198d..586e41a 100644
--- a/CHANGES.md
+++ b/CHANGES.md
@@ -7,6 +7,9 @@ Unreleased
 - {class}`Argument` accepts a `help` parameter, and help output includes
   a `Positional arguments` section when argument help is available. {issue}`2983` {pr}`3473`
 - Fix test failures when using pytest >= 9.1. {pr}`3656`
+- Fix `prompt()` and `confirm()` not stripping ANSI codes from styled prompt
+  text when the output stream does not support color, matching the behavior
+  of `echo()`. {issue}`XXXX`
 
 ## Version 8.4.2
 
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..f29b3cb 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -84,6 +85,9 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(stream):
+        text = strip_ansi(text)
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..bc9ab87 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,31 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_prompt_ansi_stripping(runner, color):
+    """click.prompt() strips ANSI codes when color=False, preserves them when color=True."""
+    styled = click.style("Hello World!", fg="green")
+
+    @click.command()
+    def cli():
+        click.prompt(styled)
+
+    result = runner.invoke(cli, input="something\n", color=color)
+    assert "Hello World!" in result.output
+    assert ("\x1b[" in result.output) == color
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_confirm_ansi_stripping(runner, color):
+    """click.confirm() strips ANSI codes when color=False, preserves them when color=True."""
+    styled = click.style("Hello World!", fg="green")
+
+    @click.command()
+    def cli():
+        click.confirm(styled, abort=True)
+
+    result = runner.invoke(cli, input="y\n", color=color)
+    assert "Hello World!" in result.output
+    assert ("\x1b[" in result.output) == color
```

**Your verdict:** 

## cal-021 (run a087beed9e)

**Criterion:** The full tests/test_parser.py file passes under the repo's pytest config with warnings as errors

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..8fc611d 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,13 @@
 import pytest
 
 import click
+import click.parser as _parser_mod
+from click.parser import _Argument
+from click.parser import _Option
 from click.parser import _OptionParser
+from click.parser import _ParsingState
+from click.parser import _normalize_opt
+from click.parser import _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +36,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_shim_warns_and_resolves(name, expected):
+    with pytest.warns(DeprecationWarning, match=f"'parser.{name}' is deprecated"):
+        result = getattr(_parser_mod, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_warns_and_resolves():
+    with pytest.warns(DeprecationWarning, match="Importing 'parser.split_arg_string' is deprecated"):
+        result = getattr(_parser_mod, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_parser_attribute_raises():
+    with pytest.raises(AttributeError):
+        getattr(_parser_mod, "no_such_name")
```

**Your verdict:** 

## cal-022 (run c6a33e9282)

**Criterion:** Tests cover actions defined in the creator updating and reading combined state via set/get

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-023 (run 8c20178c2c)

**Criterion:** A command calling click.confirm on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/CHANGES.md b/CHANGES.md
index bed198d..586e41a 100644
--- a/CHANGES.md
+++ b/CHANGES.md
@@ -7,6 +7,9 @@ Unreleased
 - {class}`Argument` accepts a `help` parameter, and help output includes
   a `Positional arguments` section when argument help is available. {issue}`2983` {pr}`3473`
 - Fix test failures when using pytest >= 9.1. {pr}`3656`
+- Fix `prompt()` and `confirm()` not stripping ANSI codes from styled prompt
+  text when the output stream does not support color, matching the behavior
+  of `echo()`. {issue}`XXXX`
 
 ## Version 8.4.2
 
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..f29b3cb 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -84,6 +85,9 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(stream):
+        text = strip_ansi(text)
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..bc9ab87 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,31 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_prompt_ansi_stripping(runner, color):
+    """click.prompt() strips ANSI codes when color=False, preserves them when color=True."""
+    styled = click.style("Hello World!", fg="green")
+
+    @click.command()
+    def cli():
+        click.prompt(styled)
+
+    result = runner.invoke(cli, input="something\n", color=color)
+    assert "Hello World!" in result.output
+    assert ("\x1b[" in result.output) == color
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_confirm_ansi_stripping(runner, color):
+    """click.confirm() strips ANSI codes when color=False, preserves them when color=True."""
+    styled = click.style("Hello World!", fg="green")
+
+    @click.command()
+    def cli():
+        click.confirm(styled, abort=True)
+
+    result = runner.invoke(cli, input="y\n", color=color)
+    assert "Hello World!" in result.output
+    assert ("\x1b[" in result.output) == color
```

**Your verdict:** 

## cal-024 (run 290a105742)

**Criterion:** shallow({ a: undefined }, { b: 1 }) returns false

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..c1dc74f 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -166,6 +166,12 @@ describe('shallow', () => {
     ).toBe(true)
   })
 
+  it('treats undefined value on missing key as a difference', () => {
+    expect(shallow({ a: undefined }, { b: 1 })).toBe(false)
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+    expect(shallow({ a: undefined }, { a: undefined })).toBe(true)
+  })
+
   it('should work with nested arrays (#2794)', () => {
     const arr = [1, 2]
     expect(shallow([arr, 1], [arr, 1])).toBe(true)
```

**Your verdict:** 

## cal-025 (run 8c45f5bf74)

**Criterion:** The whole repo still passes tsc --noEmit

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..73a474f 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -180,6 +180,30 @@ describe('counter state spec (single middleware)', () => {
     expect(testSubtyping).toBeDefined()
   })
 
+  it('devtools initializer return type is checked against store type', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    // correct initializer compiles fine
+    createStore<Store>()(
+      devtools((_set) => ({
+        attr: 0,
+        setAttr: () => {},
+      })),
+    )
+
+    // wrong initializer must not compile
+    createStore<Store>()(
+      // @ts-expect-error devtools should preserve the initializer return type for checking
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
   it('devtools #2700', () => {
     type TableStore = {
       table: string
```

**Your verdict:** 

## cal-026 (run 258b0a0736)

**Criterion:** tests/combine.test.tsx exists and passes under vitest

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-027 (run 8c20178c2c)

**Criterion:** New tests in tests/test_termui.py cover confirm and prompt with color enabled and disabled

```diff
diff --git a/CHANGES.md b/CHANGES.md
index bed198d..586e41a 100644
--- a/CHANGES.md
+++ b/CHANGES.md
@@ -7,6 +7,9 @@ Unreleased
 - {class}`Argument` accepts a `help` parameter, and help output includes
   a `Positional arguments` section when argument help is available. {issue}`2983` {pr}`3473`
 - Fix test failures when using pytest >= 9.1. {pr}`3656`
+- Fix `prompt()` and `confirm()` not stripping ANSI codes from styled prompt
+  text when the output stream does not support color, matching the behavior
+  of `echo()`. {issue}`XXXX`
 
 ## Version 8.4.2
 
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..f29b3cb 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -84,6 +85,9 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(stream):
+        text = strip_ansi(text)
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..bc9ab87 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,31 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_prompt_ansi_stripping(runner, color):
+    """click.prompt() strips ANSI codes when color=False, preserves them when color=True."""
+    styled = click.style("Hello World!", fg="green")
+
+    @click.command()
+    def cli():
+        click.prompt(styled)
+
+    result = runner.invoke(cli, input="something\n", color=color)
+    assert "Hello World!" in result.output
+    assert ("\x1b[" in result.output) == color
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_confirm_ansi_stripping(runner, color):
+    """click.confirm() strips ANSI codes when color=False, preserves them when color=True."""
+    styled = click.style("Hello World!", fg="green")
+
+    @click.command()
+    def cli():
+        click.confirm(styled, abort=True)
+
+    result = runner.invoke(cli, input="y\n", color=color)
+    assert "Hello World!" in result.output
+    assert ("\x1b[" in result.output) == color
```

**Your verdict:** 

## cal-028 (run 4db972bb2f)

**Criterion:** Tests cover merged initial state and creator-value precedence on overlapping keys

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-029 (run 7420daaea6)

**Criterion:** Completing a Choice over an Enum suggests member names such as "foo", never "MyEnum.foo"

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 3543009..959ce95 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,10 @@ Version 8.4.1
 
 Unreleased
 
+-   :class:`Choice` shell completion suggests normalized values (e.g. enum
+    member names) that the parser actually accepts, instead of raw
+    ``str()`` representations. Case-insensitive choices are suggested in
+    their lowercased form.
 -   Zsh completion scripts parse correctly on Windows. :issue:`3277`
 
 
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..0f8befe 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..42c1421 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -1,3 +1,4 @@
+import enum
 import io
 import textwrap
 import warnings
@@ -148,6 +149,30 @@ def test_type_choice():
     assert _get_words(cli, ["-c"], "a2") == ["a2"]
 
 
+def test_choice_enum_completion():
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-c"], type=Choice(MyEnum))])
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "b") == ["baz"]
+
+
+def test_choice_enum_case_insensitive():
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli", params=[Option(["-c"], type=Choice(MyEnum, case_sensitive=False))]
+    )
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "F") == ["foo"]
+
+
 def test_choice_special_characters():
     cli = Command("cli", params=[Option(["-c"], type=Choice(["!1", "!2", "+3"]))])
     assert _get_words(cli, ["-c"], "") == ["!1", "!2", "+3"]
@@ -473,7 +498,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
```

**Your verdict:** 

## cal-030 (run 7e455ac072)

**Criterion:** Output for calls with non-empty args is unchanged, including wrapping behavior

```diff
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..2f63599 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,10 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            # Nothing to wrap; write the prefix+prog without trailing space.
+            self.write(usage_prefix.rstrip())
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
@@ -176,7 +179,7 @@ class HelpFormatter:
                 )
             )
         else:
-            # The prefix is too long, put the arguments on the next line.
+            # The prefix is too long; put the arguments on the next line.
             self.write(usage_prefix)
             self.write("\n")
             indent = " " * (max(self.current_indent, term_len(prefix)) + 4)
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..613b5fd 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,35 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: prog' with no trailing whitespace."""
+    formatter = click.HelpFormatter(width=78)
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """write_usage with no args respects a custom prefix and has no trailing whitespace."""
+    formatter = click.HelpFormatter(width=78)
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_empty_args_via_command_no_params():
+    """A command with no parameters produces a usage line with no trailing whitespace."""
+
+    @click.command(add_help_option=False, options_metavar="")
+    def cmd():
+        pass
+
+    formatter = click.HelpFormatter(width=78)
+    ctx = click.Context(cmd, info_name="cmd")
+    cmd.format_usage(ctx, formatter)
+    line = formatter.getvalue().rstrip("\n")
+    assert line == "Usage: cmd"
+    assert not line.endswith(" ")
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-031 (run 8864f90759)

**Criterion:** HelpFormatter().write_usage("program") followed by getvalue() returns exactly "Usage: program" plus a newline

```diff
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..ee3c7a1 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(f"{prefix:>{self.current_indent}}{prog}")
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
@@ -188,6 +190,7 @@ class HelpFormatter:
 
         self.write("\n")
 
+
     def write_heading(self, heading: str) -> None:
         """Writes a heading into the buffer."""
         self.write(f"{'':>{self.current_indent}}{heading}:\n")
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..c29df68 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,29 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_no_args_default_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_no_args_custom_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_no_args_via_command(runner):
+    @click.command()
+    def cli():
+        pass
+
+    result = runner.invoke(cli, ["--help"])
+    assert not result.exception
+    first_line = result.output.splitlines()[0]
+    assert first_line == "Usage: cli [OPTIONS]"
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-032 (run c3eb32d18b)

**Criterion:** All existing shallow tests still pass

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..e5fe715 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -170,6 +170,10 @@ describe('shallow', () => {
     const arr = [1, 2]
     expect(shallow([arr, 1], [arr, 1])).toBe(true)
   })
+
+  it('returns false when keys differ even if first object has undefined values', () => {
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+  })
 })
 
 describe('mixed cases', () => {
```

**Your verdict:** 

## cal-033 (run a087beed9e)

**Criterion:** New tests assert the shimmed split_arg_string is the function from click.shell_completion

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..8fc611d 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,13 @@
 import pytest
 
 import click
+import click.parser as _parser_mod
+from click.parser import _Argument
+from click.parser import _Option
 from click.parser import _OptionParser
+from click.parser import _ParsingState
+from click.parser import _normalize_opt
+from click.parser import _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +36,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_shim_warns_and_resolves(name, expected):
+    with pytest.warns(DeprecationWarning, match=f"'parser.{name}' is deprecated"):
+        result = getattr(_parser_mod, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_warns_and_resolves():
+    with pytest.warns(DeprecationWarning, match="Importing 'parser.split_arg_string' is deprecated"):
+        result = getattr(_parser_mod, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_parser_attribute_raises():
+    with pytest.raises(AttributeError):
+        getattr(_parser_mod, "no_such_name")
```

**Your verdict:** 

## cal-034 (run 763eb5afdd)

**Criterion:** Suggested completions are the same normalized values that Choice.convert accepts

```diff
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..d2f4ce4 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..ed90d5b 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -1,3 +1,4 @@
+import enum
 import io
 import textwrap
 import warnings
@@ -473,7 +474,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +484,30 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum_completion():
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    completions = _get_words(cli, ["-e"], "")
+    # Completions must be the normalized names (what the parser accepts), not
+    # the raw str(enum_member) representation ("MyEnum.foo").
+    assert completions == ["foo", "baz"]
+
+
+def test_choice_enum_completion_case_insensitive():
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli", params=[Option(["-e"], type=Choice(MyEnum, case_sensitive=False))]
+    )
+    completions = _get_words(cli, ["-e"], "")
+    assert completions == ["foo", "baz"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-035 (run 032760777d)

**Criterion:** A command calling click.confirm on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..1cbc831 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -202,6 +203,12 @@ def prompt(
 
         confirmation_prompt = _build_prompt(confirmation_prompt, prompt_suffix)
 
+    _prompt_stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(_prompt_stream):
+        prompt = strip_ansi(prompt)
+        if isinstance(confirmation_prompt, str):
+            confirmation_prompt = strip_ansi(confirmation_prompt)
+
     while True:
         while True:
             value = prompt_func(prompt)
@@ -267,6 +274,9 @@ def confirm(
         "y/n" if default is None else ("Y/n" if default else "y/N"),
     )
 
+    if _compat.should_strip_ansi(sys.stderr if err else sys.stdout):
+        prompt = strip_ansi(prompt)
+
     while True:
         try:
             value = _readline_prompt(visible_prompt_func, prompt, err).lower().strip()
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..093f42b 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,44 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_confirm_ansi_in_prompt(runner, color, expect_ansi):
+    """confirm() must strip ANSI codes from the prompt when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Hello World!" in result.output
+    assert "[y/N]" in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_prompt_ansi_in_prompt(runner, color, expect_ansi):
+    """prompt() must strip ANSI codes from the prompt text when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.prompt(click.style("Enter value", fg="green"))
+
+    result = runner.invoke(cli, input="hello", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Enter value" in result.output
```

**Your verdict:** 

## cal-036 (run 032760777d)

**Criterion:** New tests in tests/test_termui.py cover confirm and prompt with color enabled and disabled

```diff
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..1cbc831 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -202,6 +203,12 @@ def prompt(
 
         confirmation_prompt = _build_prompt(confirmation_prompt, prompt_suffix)
 
+    _prompt_stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(_prompt_stream):
+        prompt = strip_ansi(prompt)
+        if isinstance(confirmation_prompt, str):
+            confirmation_prompt = strip_ansi(confirmation_prompt)
+
     while True:
         while True:
             value = prompt_func(prompt)
@@ -267,6 +274,9 @@ def confirm(
         "y/n" if default is None else ("Y/n" if default else "y/N"),
     )
 
+    if _compat.should_strip_ansi(sys.stderr if err else sys.stdout):
+        prompt = strip_ansi(prompt)
+
     while True:
         try:
             value = _readline_prompt(visible_prompt_func, prompt, err).lower().strip()
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..093f42b 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,44 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_confirm_ansi_in_prompt(runner, color, expect_ansi):
+    """confirm() must strip ANSI codes from the prompt when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Hello World!" in result.output
+    assert "[y/N]" in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_prompt_ansi_in_prompt(runner, color, expect_ansi):
+    """prompt() must strip ANSI codes from the prompt text when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.prompt(click.style("Enter value", fg="green"))
+
+    result = runner.invoke(cli, input="hello", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Enter value" in result.output
```

**Your verdict:** 

## cal-037 (run 8864f90759)

**Criterion:** Output for calls with non-empty args is unchanged, including wrapping behavior

```diff
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..ee3c7a1 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(f"{prefix:>{self.current_indent}}{prog}")
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
@@ -188,6 +190,7 @@ class HelpFormatter:
 
         self.write("\n")
 
+
     def write_heading(self, heading: str) -> None:
         """Writes a heading into the buffer."""
         self.write(f"{'':>{self.current_indent}}{heading}:\n")
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..c29df68 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,29 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_no_args_default_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_no_args_custom_prefix():
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_no_args_via_command(runner):
+    @click.command()
+    def cli():
+        pass
+
+    result = runner.invoke(cli, ["--help"])
+    assert not result.exception
+    first_line = result.output.splitlines()[0]
+    assert first_line == "Usage: cli [OPTIONS]"
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-038 (run 1cbc7c7fd0)

**Criterion:** In an environment with a non-functional globalThis.localStorage and no window, creating a persisted store and calling setState does not throw; persist falls into its existing storage-unavailable warning path

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..567947d 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -3,6 +3,7 @@
 import { afterEach, describe, expect, it, vi } from 'vitest'
 import { create } from 'zustand'
 import { createJSONStorage, persist } from 'zustand/middleware'
+import type { StateStorage } from 'zustand/middleware'
 import { replacer, reviver } from './test-utils'
 
 const createPersistentStore = (initialValue: string | null) => {
@@ -757,4 +758,48 @@ describe('persist middleware with sync configuration', () => {
     expect(useBoundStore.persist.hasHydrated()).toBe(true)
     expect(setItem).toBeCalledTimes(0)
   })
+
+  it('falls back to warning path when storage getter throws (simulates window not defined)', () => {
+    // In Node.js 25 the window identifier is absent, so () => window.localStorage
+    // throws ReferenceError. createJSONStorage catches it and returns undefined,
+    // which puts persist in the no-storage warning path instead of crashing.
+    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
+    const useStore = create(
+      persist(
+        (set) => ({
+          count: 0,
+          increment: () => set({ count: 1 }),
+        }),
+        {
+          name: 'test-node25-default',
+          storage: createJSONStorage(() => {
+            throw new ReferenceError('window is not defined')
+          }),
+        },
+      ),
+    )
+    expect(() => useStore.getState().increment()).not.toThrow()
+    expect(warnSpy).toHaveBeenCalledWith(
+      expect.stringContaining("Unable to update item 'test-node25-default'"),
+    )
+    warnSpy.mockRestore()
+  })
+
+  it('uses window.localStorage as default storage when window is available', () => {
+    const localStorageMock: StateStorage = {
+      getItem: () => null,
+      setItem: vi.fn(),
+      removeItem: vi.fn(),
+    }
+    vi.stubGlobal('localStorage', localStorageMock)
+    try {
+      const useStore = create(
+        persist(() => ({ count: 0 }), { name: 'test-node25-browser' }),
+      )
+      useStore.setState({ count: 1 })
+      expect(localStorageMock.setItem).toHaveBeenCalled()
+    } finally {
+      vi.unstubAllGlobals()
+    }
+  })
 })
```

**Your verdict:** 

## cal-039 (run c3f0af0a8e)

**Criterion:** Tests cover merged initial state and creator-value precedence on overlapping keys

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-040 (run bf4ab4ba6d)

**Criterion:** Tests cover actions defined in the creator updating and reading combined state via set/get

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-041 (run 520857f352)

**Criterion:** createStore<Store>()(devtools((set) => ({ ...wrong shape... }))) produces a type error, matching the behavior without devtools

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..f97141b 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -786,6 +786,40 @@ describe('create with explicitly annotated mutators', () => {
   })
 })
 
+describe('devtools initializer return type checking', () => {
+  it('rejects wrong-shape initializer (erased-inference regression)', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error initializer returns wrong shape: attr should be number, setAttr should be () => void
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
+  it('accepts correctly typed initializer with set/get inference', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    const store = createStore<Store>()(
+      devtools((set, get) => ({
+        attr: 0,
+        setAttr: () => set({ attr: get().attr + 1 }),
+      })),
+    )
+    expectTypeOf(store.getState().attr).toEqualTypeOf<number>()
+    expectTypeOf(store.getState().setAttr).toEqualTypeOf<() => void>()
+    expect(store).toBeDefined()
+  })
+})
+
 describe('single middleware with sliced store', () => {
   it('immer with slices where slice type differs from store (#3371)', () => {
     interface BearSlice {
```

**Your verdict:** 

## cal-042 (run 20b546c849)

**Criterion:** A type-level regression test in tests/middlewareTypes.test.tsx covers the erased-inference scenario

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..6993e49 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -198,6 +198,21 @@ describe('counter state spec (single middleware)', () => {
     expect(useStoreD).toBeDefined()
   })
 
+  it('devtools initializer return type is checked against store type', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error attr should be number not string; setAttr should be function not boolean
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
   it('subscribeWithSelector', () => {
     const useBoundStore = create<CounterState>()(
       subscribeWithSelector((set, get) => ({
```

**Your verdict:** 

## cal-043 (run 7420daaea6)

**Criterion:** Suggested completions are the same normalized values that Choice.convert accepts

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 3543009..959ce95 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,10 @@ Version 8.4.1
 
 Unreleased
 
+-   :class:`Choice` shell completion suggests normalized values (e.g. enum
+    member names) that the parser actually accepts, instead of raw
+    ``str()`` representations. Case-insensitive choices are suggested in
+    their lowercased form.
 -   Zsh completion scripts parse correctly on Windows. :issue:`3277`
 
 
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..0f8befe 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..42c1421 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -1,3 +1,4 @@
+import enum
 import io
 import textwrap
 import warnings
@@ -148,6 +149,30 @@ def test_type_choice():
     assert _get_words(cli, ["-c"], "a2") == ["a2"]
 
 
+def test_choice_enum_completion():
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-c"], type=Choice(MyEnum))])
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "b") == ["baz"]
+
+
+def test_choice_enum_case_insensitive():
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli", params=[Option(["-c"], type=Choice(MyEnum, case_sensitive=False))]
+    )
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "F") == ["foo"]
+
+
 def test_choice_special_characters():
     cli = Command("cli", params=[Option(["-c"], type=Choice(["!1", "!2", "+3"]))])
     assert _get_words(cli, ["-c"], "") == ["!1", "!2", "+3"]
@@ -473,7 +498,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
```

**Your verdict:** 

## cal-044 (run 18b7d6e137)

**Criterion:** A regression test in tests/vanilla/shallow.test.tsx covers the undefined-value key-mismatch case

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..fae59c4 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -27,6 +27,11 @@ describe('shallow', () => {
     ).toBe(false)
   })
 
+  it('treats a key present in A with undefined value as different from a missing key in B', () => {
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+    expect(shallow({ a: undefined }, { b: undefined })).toBe(false)
+  })
+
   it('compares arrays', () => {
     expect(shallow([1, 2, 3], [1, 2, 3])).toBe(true)
 
```

**Your verdict:** 

## cal-045 (run 3469c1086b)

**Criterion:** Output for calls with non-empty args is unchanged, including wrapping behavior

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..5cc77cb 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,9 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now emits the prefix and program name
+    even when ``args`` is empty, with no trailing whitespace after the program
+    name.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..45cd974 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(usage_prefix.rstrip())
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..9f70462 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,40 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: <prog>' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_empty_args_no_trailing_space():
+    """No trailing whitespace appears after the program name when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    line = formatter.getvalue().rstrip("\n")
+    assert line == line.rstrip()
+
+
+def test_write_usage_command_no_params(runner):
+    """A command with no params and no options metavar produces a clean usage line."""
+    cmd = click.Command("cmd", callback=lambda: None, add_help_option=False,
+                        options_metavar="", params=[])
+    ctx = click.Context(cmd, info_name="cmd")
+    formatter = ctx.make_formatter()
+    cmd.format_usage(ctx, formatter)
+    line = formatter.getvalue().rstrip("\n")
+    assert line == "Usage: cmd"
+    assert not line.endswith(" ")
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-046 (run 032760777d)

**Criterion:** A command calling click.prompt on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..1cbc831 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -202,6 +203,12 @@ def prompt(
 
         confirmation_prompt = _build_prompt(confirmation_prompt, prompt_suffix)
 
+    _prompt_stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(_prompt_stream):
+        prompt = strip_ansi(prompt)
+        if isinstance(confirmation_prompt, str):
+            confirmation_prompt = strip_ansi(confirmation_prompt)
+
     while True:
         while True:
             value = prompt_func(prompt)
@@ -267,6 +274,9 @@ def confirm(
         "y/n" if default is None else ("Y/n" if default else "y/N"),
     )
 
+    if _compat.should_strip_ansi(sys.stderr if err else sys.stdout):
+        prompt = strip_ansi(prompt)
+
     while True:
         try:
             value = _readline_prompt(visible_prompt_func, prompt, err).lower().strip()
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..093f42b 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,44 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_confirm_ansi_in_prompt(runner, color, expect_ansi):
+    """confirm() must strip ANSI codes from the prompt when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Hello World!" in result.output
+    assert "[y/N]" in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_prompt_ansi_in_prompt(runner, color, expect_ansi):
+    """prompt() must strip ANSI codes from the prompt text when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.prompt(click.style("Enter value", fg="green"))
+
+    result = runner.invoke(cli, input="hello", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Enter value" in result.output
```

**Your verdict:** 

## cal-047 (run c6a33e9282)

**Criterion:** No pre-existing file is modified

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-048 (run a7f858a66a)

**Criterion:** No pre-existing file is modified

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-049 (run 7d59cb5d66)

**Criterion:** A regression test in tests/vanilla/shallow.test.tsx covers the undefined-value key-mismatch case

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..40001c3 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -27,6 +27,13 @@ describe('shallow', () => {
     ).toBe(false)
   })
 
+  it('treats a key with undefined value as different from a missing key', () => {
+    // key 'a' exists on first object with value undefined, but is absent on second
+    expect(shallow({ a: undefined }, { b: 1 })).toBe(false)
+    // same key with undefined on both sides is still equal
+    expect(shallow({ a: undefined }, { a: undefined })).toBe(true)
+  })
+
   it('compares arrays', () => {
     expect(shallow([1, 2, 3], [1, 2, 3])).toBe(true)
 
```

**Your verdict:** 

## cal-050 (run b7c5fbfc09)

**Criterion:** Completing a Choice over an Enum suggests member names such as "foo", never "MyEnum.foo"

```diff
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..9c5fef0 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normalized = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normalized if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            normed_incomplete = incomplete.casefold()
+            matched = (c for c in normalized if c.startswith(normed_incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..f023c1b 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -473,7 +473,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +483,30 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum_completion():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    completions = _get_words(cli, ["-e"], "")
+    assert completions == ["foo", "baz"]
+
+
+def test_choice_enum_completion_prefix():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    completions = _get_words(cli, ["-e"], "f")
+    assert completions == ["foo"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-051 (run 2f040f7694)

**Criterion:** The full tests/test_parser.py file passes under the repo's pytest config with warnings as errors

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..95bab0b 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,8 @@
 import pytest
 
 import click
-from click.parser import _OptionParser
+import click.parser
+from click.parser import _Argument, _normalize_opt, _Option, _OptionParser, _ParsingState, _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +31,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_shim_warns(name, expected):
+    with pytest.warns(DeprecationWarning, match=f"parser\\.{name}.*deprecated"):
+        result = getattr(click.parser, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_warns():
+    with pytest.warns(DeprecationWarning, match="split_arg_string.*deprecated"):
+        result = getattr(click.parser, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_attribute_raises():
+    with pytest.raises(AttributeError):
+        click.parser.no_such_name  # type: ignore[attr-defined]
```

**Your verdict:** 

## cal-052 (run d6f740c61f)

**Criterion:** In an environment with a non-functional globalThis.localStorage and no window, creating a persisted store and calling setState does not throw; persist falls into its existing storage-unavailable warning path

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..bb27cab 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -736,6 +736,35 @@ describe('persist middleware with sync configuration', () => {
     )
   })
 
+  it('does not throw when window.localStorage access throws', () => {
+    // Simulate environments where window.localStorage is inaccessible (e.g.
+    // private-browsing SecurityError or Node.js where window is not defined).
+    // createJSONStorage swallows the error and returns undefined; persist then
+    // takes its existing no-storage code path and setState must not crash.
+    const originalDescriptor =
+      Object.getOwnPropertyDescriptor(window, 'localStorage') ??
+      Object.getOwnPropertyDescriptor(Object.getPrototypeOf(window), 'localStorage')
+    Object.defineProperty(window, 'localStorage', {
+      get() {
+        throw new DOMException('SecurityError')
+      },
+      configurable: true,
+    })
+    try {
+      // Verify the override is effective before testing persist behaviour.
+      expect(() => window.localStorage).toThrow(DOMException)
+
+      const store = create(
+        persist(() => ({ count: 0 }), { name: 'test-no-storage' }),
+      )
+      expect(() => store.setState({ count: 1 })).not.toThrow()
+    } finally {
+      if (originalDescriptor) {
+        Object.defineProperty(window, 'localStorage', originalDescriptor)
+      }
+    }
+  })
+
   it('does not call setItem when hydrating from its own storage', async () => {
     const setItem = vi.fn()
     const storage = {
```

**Your verdict:** 

## cal-053 (run 7744506f1e)

**Criterion:** Correctly typed devtools initializers still compile, including set/get inference inside the initializer

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..32705d7 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -786,6 +786,23 @@ describe('create with explicitly annotated mutators', () => {
   })
 })
 
+describe('devtools initializer type checking', () => {
+  it('devtools preserves initializer return type check (#erased-inference)', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error wrong shape: attr should be number, setAttr should be () => void
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+})
+
 describe('single middleware with sliced store', () => {
   it('immer with slices where slice type differs from store (#3371)', () => {
     interface BearSlice {
```

**Your verdict:** 

## cal-054 (run 520857f352)

**Criterion:** The whole repo still passes tsc --noEmit

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..f97141b 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -786,6 +786,40 @@ describe('create with explicitly annotated mutators', () => {
   })
 })
 
+describe('devtools initializer return type checking', () => {
+  it('rejects wrong-shape initializer (erased-inference regression)', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error initializer returns wrong shape: attr should be number, setAttr should be () => void
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
+  it('accepts correctly typed initializer with set/get inference', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    const store = createStore<Store>()(
+      devtools((set, get) => ({
+        attr: 0,
+        setAttr: () => set({ attr: get().attr + 1 }),
+      })),
+    )
+    expectTypeOf(store.getState().attr).toEqualTypeOf<number>()
+    expectTypeOf(store.getState().setAttr).toEqualTypeOf<() => void>()
+    expect(store).toBeDefined()
+  })
+})
+
 describe('single middleware with sliced store', () => {
   it('immer with slices where slice type differs from store (#3371)', () => {
     interface BearSlice {
```

**Your verdict:** 

## cal-055 (run 020ddf8b0b)

**Criterion:** Output for calls with non-empty args is unchanged, including wrapping behavior

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..db3d0c0 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,8 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now correctly emits the prefix and
+    program name when ``args`` is empty, with no trailing whitespace.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..ac2146f 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,6 +164,11 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
+        if not args:
+            self.write(usage_prefix.rstrip())
+            self.write("\n")
+            return
+
         if text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..fed802c 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -499,3 +499,34 @@ def test_write_usage_styled_prefix_keeps_options_on_one_line():
 
     visible = strip_ansi(rendered)
     assert visible == "Usage: cli [OPTIONS]\n"
+
+
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: prog\n' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    result = formatter.getvalue()
+    assert result == "Usage: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    result = formatter.getvalue()
+    assert result == "Run: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_no_params_command(runner):
+    """A command with no parameters renders a usage line without trailing space."""
+
+    @click.command()
+    def cmd():
+        """A command that takes no arguments."""
+
+    result = runner.invoke(cmd, ["--help"])
+    assert not result.exception
+    first_line = result.output.splitlines()[0]
+    assert first_line == "Usage: cmd [OPTIONS]"
```

**Your verdict:** 

## cal-056 (run bf4ab4ba6d)

**Criterion:** tests/combine.test.tsx exists and passes under vitest

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-057 (run d44918b9f0)

**Criterion:** A command calling click.confirm on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..88629ef 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -84,6 +84,16 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    from . import _compat
+
+    # Strip ANSI codes when the output stream does not support color.
+    # The prompt goes through input() directly (not echo()), so echo()'s
+    # stripping does not apply here.  We check via the module attribute so
+    # that CliRunner's monkey-patch of _compat.should_strip_ansi takes effect.
+    stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(stream):
+        text = strip_ansi(text)
+
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..d51db72 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,43 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_confirm_styled_prompt_respects_color(color: bool) -> None:
+    """confirm() must strip ANSI codes when color=False and preserve them when True."""
+
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    runner = click.testing.CliRunner()
+    result = runner.invoke(cli, input="y", color=color)
+    assert result.exit_code == 0
+    if color:
+        assert "\033[" in result.output
+        assert "Hello World!" in result.output
+    else:
+        assert "\033[" not in result.output
+        assert "Hello World! [Y/n]:" in result.output or "Hello World!" in result.output
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_prompt_styled_prompt_respects_color(color: bool) -> None:
+    """prompt() must strip ANSI codes when color=False and preserve them when True."""
+
+    @click.command()
+    def cli():
+        value = click.prompt(click.style("Enter value", fg="blue"))
+        click.echo(f"got: {value}")
+
+    runner = click.testing.CliRunner()
+    result = runner.invoke(cli, input="answer", color=color)
+    assert result.exit_code == 0
+    assert "got: answer" in result.output
+    if color:
+        assert "\033[" in result.output
+        assert "Enter value" in result.output
+    else:
+        assert "\033[" not in result.output
+        assert "Enter value" in result.output
```

**Your verdict:** 

## cal-058 (run 20b546c849)

**Criterion:** createStore<Store>()(devtools((set) => ({ ...wrong shape... }))) produces a type error, matching the behavior without devtools

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..6993e49 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -198,6 +198,21 @@ describe('counter state spec (single middleware)', () => {
     expect(useStoreD).toBeDefined()
   })
 
+  it('devtools initializer return type is checked against store type', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error attr should be number not string; setAttr should be function not boolean
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
   it('subscribeWithSelector', () => {
     const useBoundStore = create<CounterState>()(
       subscribeWithSelector((set, get) => ({
```

**Your verdict:** 

## cal-059 (run 392f2828f3)

**Criterion:** New tests assert the shimmed split_arg_string is the function from click.shell_completion

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..4139930 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,6 +1,7 @@
 import pytest
 
 import click
+import click.parser
 from click.parser import _OptionParser
 from click.shell_completion import split_arg_string
 
@@ -30,3 +31,38 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    "name",
+    ["OptionParser", "Argument", "Option", "split_opt", "normalize_opt", "ParsingState"],
+)
+def test_deprecated_parser_names_warn(name):
+    with pytest.warns(DeprecationWarning, match=f"parser\\.{name}.*deprecated"):
+        getattr(click.parser, name)
+
+
+@pytest.mark.parametrize(
+    "name",
+    ["OptionParser", "Argument", "Option", "split_opt", "normalize_opt", "ParsingState"],
+)
+def test_deprecated_parser_names_resolve(name):
+    with pytest.warns(DeprecationWarning):
+        obj = getattr(click.parser, name)
+    assert obj is not None
+
+
+def test_deprecated_split_arg_string_warns():
+    with pytest.warns(DeprecationWarning, match="split_arg_string.*deprecated"):
+        getattr(click.parser, "split_arg_string")
+
+
+def test_deprecated_split_arg_string_is_shell_completion_function():
+    with pytest.warns(DeprecationWarning):
+        shimmed = getattr(click.parser, "split_arg_string")
+    assert shimmed is split_arg_string
+
+
+def test_unknown_attribute_raises():
+    with pytest.raises(AttributeError):
+        click.parser.no_such_attribute_xyz
```

**Your verdict:** 

## cal-060 (run 461adf3943)

**Criterion:** A command calling click.prompt on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/CHANGES.md b/CHANGES.md
index bed198d..75a5101 100644
--- a/CHANGES.md
+++ b/CHANGES.md
@@ -7,6 +7,9 @@ Unreleased
 - {class}`Argument` accepts a `help` parameter, and help output includes
   a `Positional arguments` section when argument help is available. {issue}`2983` {pr}`3473`
 - Fix test failures when using pytest >= 9.1. {pr}`3656`
+- Fix regression where `prompt()` and `confirm()` did not strip ANSI escape
+  codes from styled prompt text when the output stream does not support color
+  (e.g. `CliRunner` with `color=False`). {issue}`XXXX`
 
 ## Version 8.4.2
 
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..8673d9a 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -202,6 +203,12 @@ def prompt(
 
         confirmation_prompt = _build_prompt(confirmation_prompt, prompt_suffix)
 
+    _out_stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(_out_stream, resolve_color_default()):
+        prompt = strip_ansi(prompt)
+        if isinstance(confirmation_prompt, str):
+            confirmation_prompt = strip_ansi(confirmation_prompt)
+
     while True:
         while True:
             value = prompt_func(prompt)
@@ -267,6 +274,10 @@ def confirm(
         "y/n" if default is None else ("Y/n" if default else "y/N"),
     )
 
+    _out_stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(_out_stream, resolve_color_default()):
+        prompt = strip_ansi(prompt)
+
     while True:
         try:
             value = _readline_prompt(visible_prompt_func, prompt, err).lower().strip()
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..ec0075f 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,40 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_confirm_styled_prompt_ansi(color):
+    """confirm() strips ANSI when color=False, preserves it when color=True."""
+
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    runner = click.testing.CliRunner()
+    result = runner.invoke(cli, input="y", color=color)
+    assert result.exit_code == 0
+    if color:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
+        assert "Hello World!" in result.output
+
+
+@pytest.mark.parametrize("color", [False, True])
+def test_prompt_styled_prompt_ansi(color):
+    """prompt() strips ANSI when color=False, preserves it when color=True."""
+
+    @click.command()
+    def cli():
+        value = click.prompt(click.style("Enter value", fg="blue"))
+        click.echo(value)
+
+    runner = click.testing.CliRunner()
+    result = runner.invoke(cli, input="answer", color=color)
+    assert result.exit_code == 0
+    if color:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
+        assert "Enter value" in result.output
```

**Your verdict:** 

## cal-061 (run 290a105742)

**Criterion:** All existing shallow tests still pass

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..c1dc74f 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -166,6 +166,12 @@ describe('shallow', () => {
     ).toBe(true)
   })
 
+  it('treats undefined value on missing key as a difference', () => {
+    expect(shallow({ a: undefined }, { b: 1 })).toBe(false)
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+    expect(shallow({ a: undefined }, { a: undefined })).toBe(true)
+  })
+
   it('should work with nested arrays (#2794)', () => {
     const arr = [1, 2]
     expect(shallow([arr, 1], [arr, 1])).toBe(true)
```

**Your verdict:** 

## cal-062 (run cdc8edf657)

**Criterion:** The emitted usage line has no trailing spaces after the program name

```diff
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..45cd974 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(usage_prefix.rstrip())
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..bc6a7f6 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -499,3 +499,37 @@ def test_write_usage_styled_prefix_keeps_options_on_one_line():
 
     visible = strip_ansi(rendered)
     assert visible == "Usage: cli [OPTIONS]\n"
+
+
+def test_write_usage_no_args_default_prefix():
+    """write_usage with no args emits the prefix and program name, no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("myprogram")
+    assert formatter.getvalue() == "Usage: myprogram\n"
+
+
+def test_write_usage_no_args_custom_prefix():
+    """write_usage with no args and a custom prefix uses that prefix."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("myprogram", prefix="Run: ")
+    assert formatter.getvalue() == "Run: myprogram\n"
+
+
+def test_write_usage_no_args_no_trailing_whitespace():
+    """write_usage with no args produces no trailing whitespace on the usage line."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("prog")
+    line = formatter.getvalue().splitlines()[0]
+    assert line == line.rstrip()
+
+
+def test_write_usage_no_args_via_command_context():
+    """A command with no params produces a usage line with no trailing whitespace."""
+
+    @click.command(add_help_option=False, options_metavar="")
+    def no_params():
+        pass
+
+    ctx = click.Context(no_params, info_name="no-params")
+    usage = no_params.get_usage(ctx)
+    assert usage == "Usage: no-params"
```

**Your verdict:** 

## cal-063 (run cd5f9aaa65)

**Criterion:** A regression test in tests/vanilla/shallow.test.tsx covers the undefined-value key-mismatch case

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..35d24a4 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -27,6 +27,10 @@ describe('shallow', () => {
     ).toBe(false)
   })
 
+  it('treats a key missing from the second object as a difference even when the first value is undefined', () => {
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+  })
+
   it('compares arrays', () => {
     expect(shallow([1, 2, 3], [1, 2, 3])).toBe(true)
 
```

**Your verdict:** 

## cal-064 (run 020ddf8b0b)

**Criterion:** A caller-supplied prefix is preserved when args is empty

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..db3d0c0 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,8 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now correctly emits the prefix and
+    program name when ``args`` is empty, with no trailing whitespace.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..ac2146f 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,6 +164,11 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
+        if not args:
+            self.write(usage_prefix.rstrip())
+            self.write("\n")
+            return
+
         if text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..fed802c 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -499,3 +499,34 @@ def test_write_usage_styled_prefix_keeps_options_on_one_line():
 
     visible = strip_ansi(rendered)
     assert visible == "Usage: cli [OPTIONS]\n"
+
+
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: prog\n' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    result = formatter.getvalue()
+    assert result == "Usage: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    result = formatter.getvalue()
+    assert result == "Run: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_no_params_command(runner):
+    """A command with no parameters renders a usage line without trailing space."""
+
+    @click.command()
+    def cmd():
+        """A command that takes no arguments."""
+
+    result = runner.invoke(cmd, ["--help"])
+    assert not result.exception
+    first_line = result.output.splitlines()[0]
+    assert first_line == "Usage: cmd [OPTIONS]"
```

**Your verdict:** 

## cal-065 (run c3eb32d18b)

**Criterion:** A regression test in tests/vanilla/shallow.test.tsx covers the undefined-value key-mismatch case

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..e5fe715 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -170,6 +170,10 @@ describe('shallow', () => {
     const arr = [1, 2]
     expect(shallow([arr, 1], [arr, 1])).toBe(true)
   })
+
+  it('returns false when keys differ even if first object has undefined values', () => {
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+  })
 })
 
 describe('mixed cases', () => {
```

**Your verdict:** 

## cal-066 (run 8a0d5a115a)

**Criterion:** New tests assert a DeprecationWarning is emitted for each of the seven shimmed names on click.parser

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..82c3701 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,8 @@
 import pytest
 
 import click
-from click.parser import _OptionParser
+import click.parser
+from click.parser import _Argument, _Option, _OptionParser, _ParsingState, _normalize_opt, _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +31,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_parser_shim_warns_and_resolves(name, expected):
+    with pytest.warns(DeprecationWarning, match=rf"parser\.{name}.*deprecated"):
+        result = getattr(click.parser, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_shim_warns_and_resolves():
+    with pytest.warns(DeprecationWarning, match=r"split_arg_string.*deprecated"):
+        result = getattr(click.parser, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_parser_attribute_raises_attribute_error():
+    with pytest.raises(AttributeError):
+        _ = click.parser.this_name_does_not_exist
```

**Your verdict:** 

## cal-067 (run 8a0d5a115a)

**Criterion:** New tests assert the shimmed split_arg_string is the function from click.shell_completion

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..82c3701 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,8 @@
 import pytest
 
 import click
-from click.parser import _OptionParser
+import click.parser
+from click.parser import _Argument, _Option, _OptionParser, _ParsingState, _normalize_opt, _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +31,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_parser_shim_warns_and_resolves(name, expected):
+    with pytest.warns(DeprecationWarning, match=rf"parser\.{name}.*deprecated"):
+        result = getattr(click.parser, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_shim_warns_and_resolves():
+    with pytest.warns(DeprecationWarning, match=r"split_arg_string.*deprecated"):
+        result = getattr(click.parser, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_parser_attribute_raises_attribute_error():
+    with pytest.raises(AttributeError):
+        _ = click.parser.this_name_does_not_exist
```

**Your verdict:** 

## cal-068 (run 63e8ff6213)

**Criterion:** A command calling click.prompt on a styled message, invoked via CliRunner with color=False, produces output with no ANSI escape sequences

```diff
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..ff2184b 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -84,6 +85,9 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(stream, resolve_color_default()):
+        text = strip_ansi(text)
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..a734ea7 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,42 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off-strips-ansi"),
+        pytest.param(True, True, id="color-on-preserves-ansi"),
+    ],
+)
+def test_confirm_strips_ansi_based_on_color(runner, color, expect_ansi):
+    """confirm() must strip ANSI codes from the prompt when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    assert ("\x1b[" in result.output) == expect_ansi
+    assert "Hello World!" in result.output
+    assert "[y/N]" in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off-strips-ansi"),
+        pytest.param(True, True, id="color-on-preserves-ansi"),
+    ],
+)
+def test_prompt_strips_ansi_based_on_color(runner, color, expect_ansi):
+    """prompt() must strip ANSI codes from the prompt when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.prompt(click.style("Name", fg="green"))
+
+    result = runner.invoke(cli, input="Alice", color=color)
+    assert ("\x1b[" in result.output) == expect_ansi
+    assert "Name" in result.output
```

**Your verdict:** 

## cal-069 (run 20b546c849)

**Criterion:** The whole repo still passes tsc --noEmit

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..6993e49 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -198,6 +198,21 @@ describe('counter state spec (single middleware)', () => {
     expect(useStoreD).toBeDefined()
   })
 
+  it('devtools initializer return type is checked against store type', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error attr should be number not string; setAttr should be function not boolean
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
   it('subscribeWithSelector', () => {
     const useBoundStore = create<CounterState>()(
       subscribeWithSelector((set, get) => ({
```

**Your verdict:** 

## cal-070 (run a571a59c20)

**Criterion:** Tests in tests/test_shell_completion.py cover enum-backed Choice completion

```diff
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..c5fb42f 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
             incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..9520a97 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -473,7 +473,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +483,33 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum_completion():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-e"], type=Choice(MyEnum))])
+    assert _get_words(cli, ["-e"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-e"], "f") == ["foo"]
+    assert _get_words(cli, ["-e"], "b") == ["baz"]
+
+
+def test_choice_enum_case_insensitive_completion():
+    import enum
+
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli", params=[Option(["-e"], type=Choice(MyEnum, case_sensitive=False))]
+    )
+    assert _get_words(cli, ["-e"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-e"], "f") == ["foo"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-071 (run a570b8a29f)

**Criterion:** Tests in tests/test_shell_completion.py cover enum-backed Choice completion

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 3543009..80426e8 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -6,6 +6,9 @@ Version 8.4.1
 Unreleased
 
 -   Zsh completion scripts parse correctly on Windows. :issue:`3277`
+-   :class:`Choice` shell completion suggests normalized values (e.g. enum
+    member names instead of ``MyEnum.foo``, lowercased for
+    ``case_sensitive=False``) that match what the parser accepts.
 
 
 Version 8.4.0
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..d2f4ce4 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..4bd9052 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -473,7 +473,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +483,37 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-c"], type=Choice(MyEnum))])
+    # Suggestions use member names ("foo", "baz"), not "MyEnum.foo"
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "b") == ["baz"]
+
+
+def test_choice_enum_case_insensitive():
+    import enum
+
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli",
+        params=[Option(["-c"], type=Choice(MyEnum, case_sensitive=False))],
+    )
+    # Suggestions are lowercased normalized names
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "F") == ["foo"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-072 (run 66f95ba310)

**Criterion:** For case_sensitive=False the suggestions are the normalized lowercased values, and the existing case-sensitivity completion test expectation is updated accordingly

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 3543009..e8f23c4 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -6,6 +6,9 @@ Version 8.4.1
 Unreleased
 
 -   Zsh completion scripts parse correctly on Windows. :issue:`3277`
+-   :class:`Choice` shell completion suggests normalized values (e.g. enum
+    member names) that the parser accepts, rather than raw ``str()``
+    representations. For case-insensitive choices, suggestions are lowercased.
 
 
 Version 8.4.0
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..16780ea 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,14 +408,12 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
-        if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
-        else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+        if not self.case_sensitive:
+            incomplete = incomplete.casefold()
 
+        matched = (c for c in normed_choices if c.startswith(incomplete))
         return [CompletionItem(c) for c in matched]
 
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..aeb6282 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -473,7 +473,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +483,36 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-c"], type=Choice(MyEnum))])
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "ba") == ["baz"]
+
+
+def test_choice_enum_case_insensitive():
+    import enum
+
+    class Color(enum.Enum):
+        Red = "red_value"
+        Green = "green_value"
+        Blue = "blue_value"
+
+    cli = Command(
+        "cli",
+        params=[Option(["-c"], type=Choice(Color, case_sensitive=False))],
+    )
+    assert _get_words(cli, ["-c"], "") == ["red", "green", "blue"]
+    assert _get_words(cli, ["-c"], "r") == ["red"]
+    assert _get_words(cli, ["-c"], "R") == ["red"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-073 (run 1c18c89857)

**Criterion:** New tests in tests/test_termui.py cover confirm and prompt with color enabled and disabled

```diff
diff --git a/CHANGES.md b/CHANGES.md
index bed198d..22e7a35 100644
--- a/CHANGES.md
+++ b/CHANGES.md
@@ -2,6 +2,9 @@
 
 Unreleased
 
+- Fix regression where ``prompt()`` and ``confirm()`` did not strip ANSI
+  codes from styled prompt text when the output stream does not support color,
+  unlike ``echo()``. {pr}`XXXX`
 - Supported versions of Windows enable ANSI terminal styles by default.
   Colorama is no longer a dependency and is not used. {issue}`2986` {pr}`3505`
 - {class}`Argument` accepts a `help` parameter, and help output includes
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..a379109 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -84,6 +85,8 @@ def _readline_prompt(func: t.Callable[[str], str], text: str, err: bool) -> str:
     """Call a prompt function, passing the full prompt on non-Windows so
     readline can handle line editing and cursor positioning correctly.
     """
+    if _compat.should_strip_ansi(sys.stderr if err else sys.stdout):
+        text = strip_ansi(text)
     if err:
         with redirect_stdout(sys.stderr):
             return func(text)
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..2cc7d06 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,45 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color=False strips ANSI"),
+        pytest.param(True, True, id="color=True preserves ANSI"),
+    ],
+)
+def test_confirm_styled_prompt_ansi(runner, color, expect_ansi):
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    assert result.exit_code == 0
+    assert "Hello World!" in result.output
+    if expect_ansi:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color=False strips ANSI"),
+        pytest.param(True, True, id="color=True preserves ANSI"),
+    ],
+)
+def test_prompt_styled_prompt_ansi(runner, color, expect_ansi):
+    @click.command()
+    def cli():
+        click.prompt(click.style("Enter value", fg="green"))
+
+    result = runner.invoke(cli, input="test_value", color=color)
+    assert result.exit_code == 0
+    assert "Enter value" in result.output
+    if expect_ansi:
+        assert "\x1b[" in result.output
+    else:
+        assert "\x1b[" not in result.output
```

**Your verdict:** 

## cal-074 (run 032760777d)

**Criterion:** With color=True the ANSI codes in the prompt text are preserved, matching echo behavior

```diff
diff --git a/src/click/termui.py b/src/click/termui.py
index e5e9678..1cbc831 100644
--- a/src/click/termui.py
+++ b/src/click/termui.py
@@ -11,6 +11,7 @@ from contextlib import AbstractContextManager
 from contextlib import redirect_stdout
 from gettext import gettext as _
 
+from . import _compat
 from ._compat import isatty
 from ._compat import strip_ansi
 from .exceptions import Abort
@@ -202,6 +203,12 @@ def prompt(
 
         confirmation_prompt = _build_prompt(confirmation_prompt, prompt_suffix)
 
+    _prompt_stream = sys.stderr if err else sys.stdout
+    if _compat.should_strip_ansi(_prompt_stream):
+        prompt = strip_ansi(prompt)
+        if isinstance(confirmation_prompt, str):
+            confirmation_prompt = strip_ansi(confirmation_prompt)
+
     while True:
         while True:
             value = prompt_func(prompt)
@@ -267,6 +274,9 @@ def confirm(
         "y/n" if default is None else ("Y/n" if default else "y/N"),
     )
 
+    if _compat.should_strip_ansi(sys.stderr if err else sys.stdout):
+        prompt = strip_ansi(prompt)
+
     while True:
         try:
             value = _readline_prompt(visible_prompt_func, prompt, err).lower().strip()
diff --git a/tests/test_termui.py b/tests/test_termui.py
index ce974f0..093f42b 100644
--- a/tests/test_termui.py
+++ b/tests/test_termui.py
@@ -1560,3 +1560,44 @@ def test_hide_input_value_never_leaks_when_err_true(runner):
     result = runner.invoke(cli, input="leaky\n", mix_stderr=False)
     assert "leaky" not in result.stdout
     assert "leaky" not in result.stderr
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_confirm_ansi_in_prompt(runner, color, expect_ansi):
+    """confirm() must strip ANSI codes from the prompt when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.confirm(click.style("Hello World!", fg="green"), abort=True)
+
+    result = runner.invoke(cli, input="y", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Hello World!" in result.output
+    assert "[y/N]" in result.output
+
+
+@pytest.mark.parametrize(
+    ("color", "expect_ansi"),
+    [
+        pytest.param(False, False, id="color-off strips ansi"),
+        pytest.param(True, True, id="color-on keeps ansi"),
+    ],
+)
+def test_prompt_ansi_in_prompt(runner, color, expect_ansi):
+    """prompt() must strip ANSI codes from the prompt text when color is disabled."""
+
+    @click.command()
+    def cli():
+        click.prompt(click.style("Enter value", fg="green"))
+
+    result = runner.invoke(cli, input="hello", color=color)
+    has_ansi = "\x1b[" in result.output
+    assert has_ansi == expect_ansi
+    assert "Enter value" in result.output
```

**Your verdict:** 

## cal-075 (run bf4ab4ba6d)

**Criterion:** No pre-existing file is modified

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-076 (run 2b6415c789)

**Criterion:** In an environment with a non-functional globalThis.localStorage and no window, creating a persisted store and calling setState does not throw; persist falls into its existing storage-unavailable warning path

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..5df3890 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -757,4 +757,41 @@ describe('persist middleware with sync configuration', () => {
     expect(useBoundStore.persist.hasHydrated()).toBe(true)
     expect(setItem).toBeCalledTimes(0)
   })
+
+  it('falls back to no-storage warning path when window.localStorage access throws', () => {
+    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
+    // Simulate a no-window environment (e.g., Node.js 25 without a proper browser
+    // global): make window.localStorage throw so createJSONStorage swallows the
+    // error and returns undefined, landing persist in its no-storage warning path.
+    const originalDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
+    Object.defineProperty(globalThis, 'localStorage', {
+      get() {
+        throw new TypeError('localStorage is not available')
+      },
+      configurable: true,
+    })
+
+    try {
+      const useBoundStore = create(
+        persist(
+          (set) => ({
+            count: 0,
+            inc: () => set((s: { count: number }) => ({ count: s.count + 1 })),
+          }),
+          { name: 'no-window-test' },
+        ),
+      )
+      // Calling the action uses the state-creator set, which triggers the warning
+      // in the no-storage path (unlike api.setState which is not overridden).
+      expect(() => useBoundStore.getState().inc()).not.toThrow()
+      expect(consoleWarnSpy).toHaveBeenCalledWith(
+        expect.stringContaining("Unable to update item 'no-window-test'"),
+      )
+    } finally {
+      if (originalDescriptor) {
+        Object.defineProperty(globalThis, 'localStorage', originalDescriptor)
+      }
+      consoleWarnSpy.mockRestore()
+    }
+  })
 })
```

**Your verdict:** 

## cal-077 (run 4db972bb2f)

**Criterion:** Tests cover actions defined in the creator updating and reading combined state via set/get

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-078 (run 3469c1086b)

**Criterion:** The emitted usage line has no trailing spaces after the program name

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..5cc77cb 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,9 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now emits the prefix and program name
+    even when ``args`` is empty, with no trailing whitespace after the program
+    name.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..45cd974 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(usage_prefix.rstrip())
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..9f70462 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,40 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: <prog>' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_empty_args_no_trailing_space():
+    """No trailing whitespace appears after the program name when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    line = formatter.getvalue().rstrip("\n")
+    assert line == line.rstrip()
+
+
+def test_write_usage_command_no_params(runner):
+    """A command with no params and no options metavar produces a clean usage line."""
+    cmd = click.Command("cmd", callback=lambda: None, add_help_option=False,
+                        options_metavar="", params=[])
+    ctx = click.Context(cmd, info_name="cmd")
+    formatter = ctx.make_formatter()
+    cmd.format_usage(ctx, formatter)
+    line = formatter.getvalue().rstrip("\n")
+    assert line == "Usage: cmd"
+    assert not line.endswith(" ")
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

## cal-079 (run a087beed9e)

**Criterion:** New tests assert an unknown attribute on click.parser raises AttributeError

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..8fc611d 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,13 @@
 import pytest
 
 import click
+import click.parser as _parser_mod
+from click.parser import _Argument
+from click.parser import _Option
 from click.parser import _OptionParser
+from click.parser import _ParsingState
+from click.parser import _normalize_opt
+from click.parser import _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +36,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_shim_warns_and_resolves(name, expected):
+    with pytest.warns(DeprecationWarning, match=f"'parser.{name}' is deprecated"):
+        result = getattr(_parser_mod, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_warns_and_resolves():
+    with pytest.warns(DeprecationWarning, match="Importing 'parser.split_arg_string' is deprecated"):
+        result = getattr(_parser_mod, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_parser_attribute_raises():
+    with pytest.raises(AttributeError):
+        getattr(_parser_mod, "no_such_name")
```

**Your verdict:** 

## cal-080 (run 4f86489e49)

**Criterion:** New tests assert a DeprecationWarning is emitted for each of the seven shimmed names on click.parser

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..adcb2a8 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,6 +1,7 @@
 import pytest
 
 import click
+import click.parser
 from click.parser import _OptionParser
 from click.shell_completion import split_arg_string
 
@@ -30,3 +31,46 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    "name",
+    ["OptionParser", "Argument", "Option", "split_opt", "normalize_opt", "ParsingState"],
+)
+def test_deprecated_parser_names_warn(name):
+    with pytest.warns(DeprecationWarning, match=f"parser\\.{name}"):
+        obj = getattr(click.parser, name)
+
+    assert obj is not None
+
+
+@pytest.mark.parametrize(
+    ("name", "private_name"),
+    [
+        ("OptionParser", "_OptionParser"),
+        ("Argument", "_Argument"),
+        ("Option", "_Option"),
+        ("split_opt", "_split_opt"),
+        ("normalize_opt", "_normalize_opt"),
+        ("ParsingState", "_ParsingState"),
+    ],
+)
+def test_deprecated_parser_names_resolve_to_underscore_impl(name, private_name):
+    import click.parser as _parser
+
+    with pytest.warns(DeprecationWarning):
+        obj = getattr(_parser, name)
+
+    assert obj is getattr(_parser, private_name)
+
+
+def test_deprecated_split_arg_string_warns():
+    with pytest.warns(DeprecationWarning, match="parser\\.split_arg_string"):
+        shim = getattr(click.parser, "split_arg_string")
+
+    assert shim is split_arg_string
+
+
+def test_unknown_parser_attribute_raises():
+    with pytest.raises(AttributeError):
+        click.parser.no_such_attribute_xyz
```

**Your verdict:** 

## cal-081 (run 258b0a0736)

**Criterion:** Tests cover merged initial state and creator-value precedence on overlapping keys

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-082 (run 290a105742)

**Criterion:** shallow({ a: undefined }, { a: undefined }) still returns true

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..c1dc74f 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -166,6 +166,12 @@ describe('shallow', () => {
     ).toBe(true)
   })
 
+  it('treats undefined value on missing key as a difference', () => {
+    expect(shallow({ a: undefined }, { b: 1 })).toBe(false)
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+    expect(shallow({ a: undefined }, { a: undefined })).toBe(true)
+  })
+
   it('should work with nested arrays (#2794)', () => {
     const arr = [1, 2]
     expect(shallow([arr, 1], [arr, 1])).toBe(true)
```

**Your verdict:** 

## cal-083 (run 520857f352)

**Criterion:** Correctly typed devtools initializers still compile, including set/get inference inside the initializer

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..f97141b 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -786,6 +786,40 @@ describe('create with explicitly annotated mutators', () => {
   })
 })
 
+describe('devtools initializer return type checking', () => {
+  it('rejects wrong-shape initializer (erased-inference regression)', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    createStore<Store>()(
+      // @ts-expect-error initializer returns wrong shape: attr should be number, setAttr should be () => void
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
+  it('accepts correctly typed initializer with set/get inference', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    const store = createStore<Store>()(
+      devtools((set, get) => ({
+        attr: 0,
+        setAttr: () => set({ attr: get().attr + 1 }),
+      })),
+    )
+    expectTypeOf(store.getState().attr).toEqualTypeOf<number>()
+    expectTypeOf(store.getState().setAttr).toEqualTypeOf<() => void>()
+    expect(store).toBeDefined()
+  })
+})
+
 describe('single middleware with sliced store', () => {
   it('immer with slices where slice type differs from store (#3371)', () => {
     interface BearSlice {
```

**Your verdict:** 

## cal-084 (run a7f858a66a)

**Criterion:** Tests cover actions defined in the creator updating and reading combined state via set/get

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-085 (run 59dd13e824)

**Criterion:** Existing persist behavior in browser-like environments is unchanged and the persist test suites still pass

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..78a9a4b 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -736,6 +736,38 @@ describe('persist middleware with sync configuration', () => {
     )
   })
 
+  it('falls into no-storage-available path when window.localStorage throws (Node.js 25 stub scenario)', () => {
+    // Simulate environments where window.localStorage is inaccessible — e.g. Node.js 25
+    // with --localstorage-file and a bad path: window is undefined but
+    // globalThis.localStorage is a truthy stub whose setItem is not a function.
+    // With the fix, () => window.localStorage throws, createJSONStorage returns
+    // undefined, and persist takes the no-storage path instead of crashing on setState.
+    const descriptor = Object.getOwnPropertyDescriptor(window, 'localStorage')
+    Object.defineProperty(window, 'localStorage', {
+      get() {
+        throw new TypeError('localStorage unavailable')
+      },
+      configurable: true,
+    })
+
+    try {
+      const useBoundStore = create(
+        persist(() => ({ count: 0 }), { name: 'test-no-window-storage' }),
+      )
+      // Must not throw even though the default storage is unavailable
+      useBoundStore.setState({ count: 1 })
+      expect(useBoundStore.getState()).toEqual({ count: 1 })
+      // persist fell into the no-storage path so its API was never attached
+      expect((useBoundStore as any).persist).toBeUndefined()
+    } finally {
+      if (descriptor) {
+        Object.defineProperty(window, 'localStorage', descriptor)
+      } else {
+        delete (window as any).localStorage
+      }
+    }
+  })
+
   it('does not call setItem when hydrating from its own storage', async () => {
     const setItem = vi.fn()
     const storage = {
```

**Your verdict:** 

## cal-086 (run 09e4afcf65)

**Criterion:** In an environment with a non-functional globalThis.localStorage and no window, creating a persisted store and calling setState does not throw; persist falls into its existing storage-unavailable warning path

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..c31926c 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -736,6 +736,47 @@ describe('persist middleware with sync configuration', () => {
     )
   })
 
+  it('createJSONStorage returns undefined when the storage getter throws (simulates window not defined)', () => {
+    // In Node.js, accessing window.localStorage throws ReferenceError.
+    // createJSONStorage must return undefined so persist falls through to its warning path.
+    const result = createJSONStorage(() => {
+      throw new ReferenceError('window is not defined')
+    })
+    expect(result).toBeUndefined()
+  })
+
+  it('falls back to no-storage warning path when window.localStorage is inaccessible', () => {
+    // Simulates the Node.js 25 scenario: globalThis.localStorage is a truthy stub without
+    // setItem, but window is not defined so () => window.localStorage throws and
+    // createJSONStorage returns undefined, steering persist into the warning path.
+    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
+
+    try {
+      const useBoundStore = create<{ count: number; increment: () => void }>()(
+        persist(
+          (set) => ({
+            count: 0,
+            increment: () => set((s) => ({ count: s.count + 1 })),
+          }),
+          {
+            name: 'test-storage',
+            storage: createJSONStorage(() => {
+              throw new ReferenceError('window is not defined')
+            }),
+          },
+        ),
+      )
+
+      // increment() calls the internal set(), which is the wrapped one that warns
+      expect(() => useBoundStore.getState().increment()).not.toThrow()
+      expect(consoleWarnSpy).toHaveBeenCalledWith(
+        expect.stringContaining("Unable to update item 'test-storage'"),
+      )
+    } finally {
+      consoleWarnSpy.mockRestore()
+    }
+  })
+
   it('does not call setItem when hydrating from its own storage', async () => {
     const setItem = vi.fn()
     const storage = {
```

**Your verdict:** 

## cal-087 (run 020ddf8b0b)

**Criterion:** HelpFormatter().write_usage("program") followed by getvalue() returns exactly "Usage: program" plus a newline

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..db3d0c0 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,8 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now correctly emits the prefix and
+    program name when ``args`` is empty, with no trailing whitespace.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..ac2146f 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,6 +164,11 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
+        if not args:
+            self.write(usage_prefix.rstrip())
+            self.write("\n")
+            return
+
         if text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..fed802c 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -499,3 +499,34 @@ def test_write_usage_styled_prefix_keeps_options_on_one_line():
 
     visible = strip_ansi(rendered)
     assert visible == "Usage: cli [OPTIONS]\n"
+
+
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: prog\n' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    result = formatter.getvalue()
+    assert result == "Usage: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    result = formatter.getvalue()
+    assert result == "Run: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_no_params_command(runner):
+    """A command with no parameters renders a usage line without trailing space."""
+
+    @click.command()
+    def cmd():
+        """A command that takes no arguments."""
+
+    result = runner.invoke(cmd, ["--help"])
+    assert not result.exception
+    first_line = result.output.splitlines()[0]
+    assert first_line == "Usage: cmd [OPTIONS]"
```

**Your verdict:** 

## cal-088 (run 7420daaea6)

**Criterion:** Tests in tests/test_shell_completion.py cover enum-backed Choice completion

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 3543009..959ce95 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,10 @@ Version 8.4.1
 
 Unreleased
 
+-   :class:`Choice` shell completion suggests normalized values (e.g. enum
+    member names) that the parser actually accepts, instead of raw
+    ``str()`` representations. Case-insensitive choices are suggested in
+    their lowercased form.
 -   Zsh completion scripts parse correctly on Windows. :issue:`3277`
 
 
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..0f8befe 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..42c1421 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -1,3 +1,4 @@
+import enum
 import io
 import textwrap
 import warnings
@@ -148,6 +149,30 @@ def test_type_choice():
     assert _get_words(cli, ["-c"], "a2") == ["a2"]
 
 
+def test_choice_enum_completion():
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-c"], type=Choice(MyEnum))])
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "b") == ["baz"]
+
+
+def test_choice_enum_case_insensitive():
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli", params=[Option(["-c"], type=Choice(MyEnum, case_sensitive=False))]
+    )
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "F") == ["foo"]
+
+
 def test_choice_special_characters():
     cli = Command("cli", params=[Option(["-c"], type=Choice(["!1", "!2", "+3"]))])
     assert _get_words(cli, ["-c"], "") == ["!1", "!2", "+3"]
@@ -473,7 +498,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
```

**Your verdict:** 

## cal-089 (run 020ddf8b0b)

**Criterion:** The emitted usage line has no trailing spaces after the program name

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..db3d0c0 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,8 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now correctly emits the prefix and
+    program name when ``args`` is empty, with no trailing whitespace.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..ac2146f 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,6 +164,11 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
+        if not args:
+            self.write(usage_prefix.rstrip())
+            self.write("\n")
+            return
+
         if text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..fed802c 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -499,3 +499,34 @@ def test_write_usage_styled_prefix_keeps_options_on_one_line():
 
     visible = strip_ansi(rendered)
     assert visible == "Usage: cli [OPTIONS]\n"
+
+
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: prog\n' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    result = formatter.getvalue()
+    assert result == "Usage: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    result = formatter.getvalue()
+    assert result == "Run: program\n"
+    assert not result.rstrip("\n").endswith(" ")
+
+
+def test_write_usage_empty_args_no_params_command(runner):
+    """A command with no parameters renders a usage line without trailing space."""
+
+    @click.command()
+    def cmd():
+        """A command that takes no arguments."""
+
+    result = runner.invoke(cmd, ["--help"])
+    assert not result.exception
+    first_line = result.output.splitlines()[0]
+    assert first_line == "Usage: cmd [OPTIONS]"
```

**Your verdict:** 

## cal-090 (run a570b8a29f)

**Criterion:** For case_sensitive=False the suggestions are the normalized lowercased values, and the existing case-sensitivity completion test expectation is updated accordingly

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 3543009..80426e8 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -6,6 +6,9 @@ Version 8.4.1
 Unreleased
 
 -   Zsh completion scripts parse correctly on Windows. :issue:`3277`
+-   :class:`Choice` shell completion suggests normalized values (e.g. enum
+    member names instead of ``MyEnum.foo``, lowercased for
+    ``case_sensitive=False``) that match what the parser accepts.
 
 
 Version 8.4.0
diff --git a/src/click/types.py b/src/click/types.py
index 556f20f..d2f4ce4 100644
--- a/src/click/types.py
+++ b/src/click/types.py
@@ -408,13 +408,13 @@ class Choice(ParamType[ParamTypeValue], t.Generic[ParamTypeValue]):
         """
         from click.shell_completion import CompletionItem
 
-        str_choices = map(str, self.choices)
+        normed_choices = self._normalized_mapping(ctx=ctx).values()
 
         if self.case_sensitive:
-            matched = (c for c in str_choices if c.startswith(incomplete))
+            matched = (c for c in normed_choices if c.startswith(incomplete))
         else:
-            incomplete = incomplete.lower()
-            matched = (c for c in str_choices if c.lower().startswith(incomplete))
+            incomplete = incomplete.casefold()
+            matched = (c for c in normed_choices if c.startswith(incomplete))
 
         return [CompletionItem(c) for c in matched]
 
diff --git a/tests/test_shell_completion.py b/tests/test_shell_completion.py
index 23c5ff0..4bd9052 100644
--- a/tests/test_shell_completion.py
+++ b/tests/test_shell_completion.py
@@ -473,7 +473,7 @@ def test_context_settings(runner):
     assert result.output == "plain,a\nplain,b\n"
 
 
-@pytest.mark.parametrize(("value", "expect"), [(False, ["Au", "al"]), (True, ["al"])])
+@pytest.mark.parametrize(("value", "expect"), [(False, ["au", "al"]), (True, ["al"])])
 def test_choice_case_sensitive(value, expect):
     cli = Command(
         "cli",
@@ -483,6 +483,37 @@ def test_choice_case_sensitive(value, expect):
     assert completions == expect
 
 
+def test_choice_enum():
+    import enum
+
+    class MyEnum(enum.Enum):
+        foo = "bar"
+        baz = "qux"
+
+    cli = Command("cli", params=[Option(["-c"], type=Choice(MyEnum))])
+    # Suggestions use member names ("foo", "baz"), not "MyEnum.foo"
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "b") == ["baz"]
+
+
+def test_choice_enum_case_insensitive():
+    import enum
+
+    class MyEnum(enum.Enum):
+        Foo = "bar"
+        BAZ = "qux"
+
+    cli = Command(
+        "cli",
+        params=[Option(["-c"], type=Choice(MyEnum, case_sensitive=False))],
+    )
+    # Suggestions are lowercased normalized names
+    assert _get_words(cli, ["-c"], "") == ["foo", "baz"]
+    assert _get_words(cli, ["-c"], "f") == ["foo"]
+    assert _get_words(cli, ["-c"], "F") == ["foo"]
+
+
 @pytest.fixture()
 def _restore_available_shells(tmpdir):
     prev_available_shells = click.shell_completion._available_shells.copy()
```

**Your verdict:** 

## cal-091 (run c3eb32d18b)

**Criterion:** shallow({ a: undefined }, { b: 1 }) returns false

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..e5fe715 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -170,6 +170,10 @@ describe('shallow', () => {
     const arr = [1, 2]
     expect(shallow([arr, 1], [arr, 1])).toBe(true)
   })
+
+  it('returns false when keys differ even if first object has undefined values', () => {
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+  })
 })
 
 describe('mixed cases', () => {
```

**Your verdict:** 

## cal-092 (run 8c45f5bf74)

**Criterion:** createStore<Store>()(devtools((set) => ({ ...wrong shape... }))) produces a type error, matching the behavior without devtools

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..73a474f 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -180,6 +180,30 @@ describe('counter state spec (single middleware)', () => {
     expect(testSubtyping).toBeDefined()
   })
 
+  it('devtools initializer return type is checked against store type', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    // correct initializer compiles fine
+    createStore<Store>()(
+      devtools((_set) => ({
+        attr: 0,
+        setAttr: () => {},
+      })),
+    )
+
+    // wrong initializer must not compile
+    createStore<Store>()(
+      // @ts-expect-error devtools should preserve the initializer return type for checking
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
   it('devtools #2700', () => {
     type TableStore = {
       table: string
```

**Your verdict:** 

## cal-093 (run 8a0d5a115a)

**Criterion:** The full tests/test_parser.py file passes under the repo's pytest config with warnings as errors

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..82c3701 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,8 @@
 import pytest
 
 import click
-from click.parser import _OptionParser
+import click.parser
+from click.parser import _Argument, _Option, _OptionParser, _ParsingState, _normalize_opt, _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +31,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_parser_shim_warns_and_resolves(name, expected):
+    with pytest.warns(DeprecationWarning, match=rf"parser\.{name}.*deprecated"):
+        result = getattr(click.parser, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_shim_warns_and_resolves():
+    with pytest.warns(DeprecationWarning, match=r"split_arg_string.*deprecated"):
+        result = getattr(click.parser, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_parser_attribute_raises_attribute_error():
+    with pytest.raises(AttributeError):
+        _ = click.parser.this_name_does_not_exist
```

**Your verdict:** 

## cal-094 (run 18b7d6e137)

**Criterion:** shallow({ a: undefined }, { a: undefined }) still returns true

```diff
diff --git a/src/vanilla/shallow.ts b/src/vanilla/shallow.ts
index 1fb8631..2621ef8 100644
--- a/src/vanilla/shallow.ts
+++ b/src/vanilla/shallow.ts
@@ -19,7 +19,7 @@ const compareEntries = (
     return false
   }
   for (const [key, value] of mapA) {
-    if (!Object.is(value, mapB.get(key))) {
+    if (!mapB.has(key) || !Object.is(value, mapB.get(key))) {
       return false
     }
   }
diff --git a/tests/vanilla/shallow.test.tsx b/tests/vanilla/shallow.test.tsx
index e99f048..fae59c4 100644
--- a/tests/vanilla/shallow.test.tsx
+++ b/tests/vanilla/shallow.test.tsx
@@ -27,6 +27,11 @@ describe('shallow', () => {
     ).toBe(false)
   })
 
+  it('treats a key present in A with undefined value as different from a missing key in B', () => {
+    expect(shallow({ '1': undefined }, { '2': { x: 1 } })).toBe(false)
+    expect(shallow({ a: undefined }, { b: undefined })).toBe(false)
+  })
+
   it('compares arrays', () => {
     expect(shallow([1, 2, 3], [1, 2, 3])).toBe(true)
 
```

**Your verdict:** 

## cal-095 (run 8c45f5bf74)

**Criterion:** Correctly typed devtools initializers still compile, including set/get inference inside the initializer

```diff
diff --git a/src/middleware/devtools.ts b/src/middleware/devtools.ts
index a882655..cbbe683 100644
--- a/src/middleware/devtools.ts
+++ b/src/middleware/devtools.ts
@@ -96,7 +96,7 @@ type Devtools = <
 >(
   initializer: StateCreator<T, [...Mps, ['zustand/devtools', never]], Mcs, U>,
   devtoolsOptions?: DevtoolsOptions,
-) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs]>
+) => StateCreator<T, Mps, [['zustand/devtools', never], ...Mcs], U>
 
 type DevtoolsImpl = <T>(
   storeInitializer: StateCreator<T, [], []>,
diff --git a/tests/middlewareTypes.test.tsx b/tests/middlewareTypes.test.tsx
index ec941ff..73a474f 100644
--- a/tests/middlewareTypes.test.tsx
+++ b/tests/middlewareTypes.test.tsx
@@ -180,6 +180,30 @@ describe('counter state spec (single middleware)', () => {
     expect(testSubtyping).toBeDefined()
   })
 
+  it('devtools initializer return type is checked against store type', () => {
+    interface Store {
+      attr: number
+      setAttr: () => void
+    }
+
+    // correct initializer compiles fine
+    createStore<Store>()(
+      devtools((_set) => ({
+        attr: 0,
+        setAttr: () => {},
+      })),
+    )
+
+    // wrong initializer must not compile
+    createStore<Store>()(
+      // @ts-expect-error devtools should preserve the initializer return type for checking
+      devtools((_set) => ({
+        attr: 'string',
+        setAttr: false,
+      })),
+    )
+  })
+
   it('devtools #2700', () => {
     type TableStore = {
       table: string
```

**Your verdict:** 

## cal-096 (run c3f0af0a8e)

**Criterion:** Tests cover actions defined in the creator updating and reading combined state via set/get

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-097 (run 2f040f7694)

**Criterion:** New tests assert an unknown attribute on click.parser raises AttributeError

```diff
diff --git a/tests/test_parser.py b/tests/test_parser.py
index f2a3ad5..95bab0b 100644
--- a/tests/test_parser.py
+++ b/tests/test_parser.py
@@ -1,7 +1,8 @@
 import pytest
 
 import click
-from click.parser import _OptionParser
+import click.parser
+from click.parser import _Argument, _normalize_opt, _Option, _OptionParser, _ParsingState, _split_opt
 from click.shell_completion import split_arg_string
 
 
@@ -30,3 +31,31 @@ def test_parser_collects_prefixes():
     click.Option("+p", is_flag=True).add_to_parser(parser, ctx)
     click.Option("!e", is_flag=True).add_to_parser(parser, ctx)
     assert parser._opt_prefixes == {"-", "--", "+", "!"}
+
+
+@pytest.mark.parametrize(
+    ("name", "expected"),
+    [
+        ("OptionParser", _OptionParser),
+        ("Argument", _Argument),
+        ("Option", _Option),
+        ("split_opt", _split_opt),
+        ("normalize_opt", _normalize_opt),
+        ("ParsingState", _ParsingState),
+    ],
+)
+def test_deprecated_shim_warns(name, expected):
+    with pytest.warns(DeprecationWarning, match=f"parser\\.{name}.*deprecated"):
+        result = getattr(click.parser, name)
+    assert result is expected
+
+
+def test_deprecated_split_arg_string_warns():
+    with pytest.warns(DeprecationWarning, match="split_arg_string.*deprecated"):
+        result = getattr(click.parser, "split_arg_string")
+    assert result is split_arg_string
+
+
+def test_unknown_attribute_raises():
+    with pytest.raises(AttributeError):
+        click.parser.no_such_name  # type: ignore[attr-defined]
```

**Your verdict:** 

## cal-098 (run bf4ab4ba6d)

**Criterion:** Tests cover merged initial state and creator-value precedence on overlapping keys

```diff
(empty diff: no tracked changes)
```

**Your verdict:** 

## cal-099 (run 09e4afcf65)

**Criterion:** Existing persist behavior in browser-like environments is unchanged and the persist test suites still pass

```diff
diff --git a/src/middleware/persist.ts b/src/middleware/persist.ts
index 9861733..5de174d 100644
--- a/src/middleware/persist.ts
+++ b/src/middleware/persist.ts
@@ -73,7 +73,7 @@ export interface PersistOptions<
    * Combining `createJSONStorage` helps creating a persist storage
    * with JSON.parse and JSON.stringify.
    *
-   * @default createJSONStorage(() => localStorage)
+   * @default createJSONStorage(() => window.localStorage)
    */
   storage?: PersistStorage<PersistedState, PersistReturn> | undefined
   /**
@@ -187,7 +187,7 @@ const toThenable =
 const persistImpl: PersistImpl = (config, baseOptions) => (set, get, api) => {
   type S = ReturnType<typeof config>
   let options = {
-    storage: createJSONStorage<S, void>(() => localStorage),
+    storage: createJSONStorage<S, void>(() => window.localStorage),
     partialize: (state: S) => state,
     version: 0,
     merge: (persistedState: unknown, currentState: S) => ({
diff --git a/tests/persistSync.test.tsx b/tests/persistSync.test.tsx
index c1663c8..c31926c 100644
--- a/tests/persistSync.test.tsx
+++ b/tests/persistSync.test.tsx
@@ -736,6 +736,47 @@ describe('persist middleware with sync configuration', () => {
     )
   })
 
+  it('createJSONStorage returns undefined when the storage getter throws (simulates window not defined)', () => {
+    // In Node.js, accessing window.localStorage throws ReferenceError.
+    // createJSONStorage must return undefined so persist falls through to its warning path.
+    const result = createJSONStorage(() => {
+      throw new ReferenceError('window is not defined')
+    })
+    expect(result).toBeUndefined()
+  })
+
+  it('falls back to no-storage warning path when window.localStorage is inaccessible', () => {
+    // Simulates the Node.js 25 scenario: globalThis.localStorage is a truthy stub without
+    // setItem, but window is not defined so () => window.localStorage throws and
+    // createJSONStorage returns undefined, steering persist into the warning path.
+    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
+
+    try {
+      const useBoundStore = create<{ count: number; increment: () => void }>()(
+        persist(
+          (set) => ({
+            count: 0,
+            increment: () => set((s) => ({ count: s.count + 1 })),
+          }),
+          {
+            name: 'test-storage',
+            storage: createJSONStorage(() => {
+              throw new ReferenceError('window is not defined')
+            }),
+          },
+        ),
+      )
+
+      // increment() calls the internal set(), which is the wrapped one that warns
+      expect(() => useBoundStore.getState().increment()).not.toThrow()
+      expect(consoleWarnSpy).toHaveBeenCalledWith(
+        expect.stringContaining("Unable to update item 'test-storage'"),
+      )
+    } finally {
+      consoleWarnSpy.mockRestore()
+    }
+  })
+
   it('does not call setItem when hydrating from its own storage', async () => {
     const setItem = vi.fn()
     const storage = {
```

**Your verdict:** 

## cal-100 (run 3469c1086b)

**Criterion:** A caller-supplied prefix is preserved when args is empty

```diff
diff --git a/CHANGES.rst b/CHANGES.rst
index 63cb2a3..5cc77cb 100644
--- a/CHANGES.rst
+++ b/CHANGES.rst
@@ -5,6 +5,9 @@ Version 8.4.0
 
 Unreleased
 
+-   :meth:`HelpFormatter.write_usage` now emits the prefix and program name
+    even when ``args`` is empty, with no trailing whitespace after the program
+    name.
 -   :class:`ParamType` typing improvements. :pr:`3371`
 
     -   :class:`ParamType` is now a generic abstract base class,
diff --git a/src/click/formatting.py b/src/click/formatting.py
index d9075ca..45cd974 100644
--- a/src/click/formatting.py
+++ b/src/click/formatting.py
@@ -164,7 +164,9 @@ class HelpFormatter:
         usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
         text_width = self.width - self.current_indent
 
-        if text_width >= (term_len(usage_prefix) + 20):
+        if not args:
+            self.write(usage_prefix.rstrip())
+        elif text_width >= (term_len(usage_prefix) + 20):
             # The arguments will fit to the right of the prefix.
             indent = " " * term_len(usage_prefix)
             self.write(
diff --git a/tests/test_formatting.py b/tests/test_formatting.py
index 3e85688..9f70462 100644
--- a/tests/test_formatting.py
+++ b/tests/test_formatting.py
@@ -487,6 +487,40 @@ def test_wrap_text_visible_width(body, width, initial_indent):
     assert styled_visible == plain.splitlines()
 
 
+def test_write_usage_empty_args_default_prefix():
+    """write_usage with no args emits 'Usage: <prog>' with no trailing space."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    assert formatter.getvalue() == "Usage: program\n"
+
+
+def test_write_usage_empty_args_custom_prefix():
+    """A caller-supplied prefix is preserved when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program", prefix="Run: ")
+    assert formatter.getvalue() == "Run: program\n"
+
+
+def test_write_usage_empty_args_no_trailing_space():
+    """No trailing whitespace appears after the program name when args is empty."""
+    formatter = click.HelpFormatter()
+    formatter.write_usage("program")
+    line = formatter.getvalue().rstrip("\n")
+    assert line == line.rstrip()
+
+
+def test_write_usage_command_no_params(runner):
+    """A command with no params and no options metavar produces a clean usage line."""
+    cmd = click.Command("cmd", callback=lambda: None, add_help_option=False,
+                        options_metavar="", params=[])
+    ctx = click.Context(cmd, info_name="cmd")
+    formatter = ctx.make_formatter()
+    cmd.format_usage(ctx, formatter)
+    line = formatter.getvalue().rstrip("\n")
+    assert line == "Usage: cmd"
+    assert not line.endswith(" ")
+
+
 def test_write_usage_styled_prefix_keeps_options_on_one_line():
     """End-to-end: a downstream-styled ``Usage:`` prefix should not split
     ``[OPTIONS]`` across two lines.
```

**Your verdict:** 

