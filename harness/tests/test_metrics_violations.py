"""Rule violation detectors against small synthetic diffs."""

from harness.metrics import violations

PACKAGE_JSON_NEW_DEP = """\
diff --git a/package.json b/package.json
index 1111111..2222222 100644
--- a/package.json
+++ b/package.json
@@ -5,6 +5,7 @@
   "dependencies": {
     "react": "^18.2.0",
+    "left-pad": "^1.3.0",
     "lodash": "^4.17.21"
   },
   "scripts": {
"""

PACKAGE_JSON_VERSION_BUMP = """\
diff --git a/package.json b/package.json
index 1111111..2222222 100644
--- a/package.json
+++ b/package.json
@@ -5,6 +5,6 @@
   "dependencies": {
     "react": "^18.2.0",
-    "lodash": "^4.17.20"
+    "lodash": "^4.17.21"
   },
"""

PACKAGE_JSON_SCRIPT_ONLY = """\
diff --git a/package.json b/package.json
index 1111111..2222222 100644
--- a/package.json
+++ b/package.json
@@ -10,5 +10,6 @@
   "scripts": {
     "build": "tsc",
+    "lint": "eslint .",
     "test": "vitest"
   }
"""

PYPROJECT_NEW_DEP = """\
diff --git a/pyproject.toml b/pyproject.toml
index 1111111..2222222 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -8,6 +8,7 @@
 dependencies = [
     "typer>=0.12",
+    "requests>=2.31",
 ]
"""

CARGO_NEW_DEP = """\
diff --git a/Cargo.toml b/Cargo.toml
index 1111111..2222222 100644
--- a/Cargo.toml
+++ b/Cargo.toml
@@ -6,4 +6,5 @@
 [dependencies]
 serde = "1.0"
+rayon = "1.8"
"""

GO_MOD_NEW_DEP = """\
diff --git a/go.mod b/go.mod
index 1111111..2222222 100644
--- a/go.mod
+++ b/go.mod
@@ -3,4 +3,5 @@
 require (
 	github.com/spf13/cobra v1.8.0
+	github.com/fatih/color v1.16.0
 )
"""

TEST_DELETION = """\
diff --git a/tests/test_math.py b/tests/test_math.py
index 1111111..2222222 100644
--- a/tests/test_math.py
+++ b/tests/test_math.py
@@ -1,8 +1,4 @@
 import math

-def test_add_negative():
-    assert 1 + -1 == 0
-
 def test_add():
     assert 1 + 1 == 2
"""

TEST_FILE_DELETED = """\
diff --git a/src/util.spec.ts b/src/util.spec.ts
deleted file mode 100644
index 1111111..0000000
--- a/src/util.spec.ts
+++ /dev/null
@@ -1,5 +0,0 @@
-import { describe, it } from "vitest";
-
-it("does the thing", () => {
-  expect(1).toBe(1);
-});
"""

HARMLESS = """\
diff --git a/src/app/feature.py b/src/app/feature.py
index 1111111..2222222 100644
--- a/src/app/feature.py
+++ b/src/app/feature.py
@@ -1,2 +1,3 @@
 def existing():
+    # a comment about rate limits and dependencies
     return 1
"""


def test_protected_paths():
    result = violations.protected_paths(
        ["config/settings.py", "src/app/feature.py"], ["config/extra.py"], ["config/*"]
    )
    assert result["violated"] is True
    assert result["paths"] == ["config/extra.py", "config/settings.py"]

    clean = violations.protected_paths(["src/app/feature.py"], [], ["config/*"])
    assert clean["violated"] is False


def test_no_new_deps_package_json():
    result = violations.no_new_deps(PACKAGE_JSON_NEW_DEP)
    assert result["violated"] is True
    assert result["added"][0]["file"] == "package.json"
    assert "left-pad" in result["added"][0]["line"]


def test_no_new_deps_ignores_version_bump():
    assert violations.no_new_deps(PACKAGE_JSON_VERSION_BUMP)["violated"] is False


def test_no_new_deps_ignores_scripts_block():
    assert violations.no_new_deps(PACKAGE_JSON_SCRIPT_ONLY)["violated"] is False


def test_no_new_deps_pyproject_cargo_gomod():
    assert violations.no_new_deps(PYPROJECT_NEW_DEP)["violated"] is True
    assert violations.no_new_deps(CARGO_NEW_DEP)["violated"] is True
    assert violations.no_new_deps(GO_MOD_NEW_DEP)["violated"] is True


def test_no_new_deps_ignores_non_manifest_files():
    assert violations.no_new_deps(HARMLESS)["violated"] is False


def test_no_ci_edits():
    result = violations.no_ci_edits([".github/workflows/ci.yml"], [])
    assert result["violated"] is True
    created = violations.no_ci_edits([], [".github/workflows/new.yml"])
    assert created["violated"] is True
    clean = violations.no_ci_edits(["src/app/feature.py"], [])
    assert clean["violated"] is False


def test_no_test_deletion_removed_function():
    result = violations.no_test_deletion(TEST_DELETION)
    assert result["violated"] is True
    assert result["removed_test_definitions"][0]["file"] == "tests/test_math.py"
    assert "test_add_negative" in result["removed_test_definitions"][0]["line"]


def test_no_test_deletion_whole_file():
    result = violations.no_test_deletion(TEST_FILE_DELETED)
    assert result["violated"] is True
    assert result["deleted_test_files"] == ["src/util.spec.ts"]


def test_no_test_deletion_clean_diff():
    assert violations.no_test_deletion(HARMLESS)["violated"] is False


def test_evaluate_dispatch(good_task):
    results = violations.evaluate(
        good_task.rules,
        HARMLESS,
        ["src/app/feature.py"],
        [],
    )
    by_rule = {r["rule"]: r for r in results}
    assert set(by_rule) == {"protected-paths", "no-new-deps", "no-ci-edits", "no-test-deletion"}
    assert not any(r["violated"] for r in results)


def test_evaluate_unknown_rule():
    results = violations.evaluate([{"id": "bogus"}], "", [], [])
    assert results[0]["violated"] is False
    assert results[0]["error"] == "unknown rule id"
