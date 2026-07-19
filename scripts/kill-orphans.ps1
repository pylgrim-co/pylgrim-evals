# kill-orphans.ps1 — the practiced recovery sweep, scripted.
#
# Kills orphaned process trees left behind when a drain dies (machine
# sleep, TaskStop, crash). Orphan = a process whose parent PID no longer
# exists. Swept classes:
#   - shell/build tools by name (git, python, uv, bash, sh, cmd, conhost,
#     pnpm, bun, cargo, go)
#   - claude/node ONLY when their command line carries the harness
#     signature (--dangerously-skip-permissions), so interactive Claude
#     Code sessions and unrelated node apps are never touched.
#
# HARD RULE: only run this when NO drain should be running. The live
# drain's own worker shells are orphan-parented BY DESIGN under the task
# harness, so this sweep cannot tell them from dead remnants and WILL
# kill a running drain (verified live, 2026-07-19). The safe sequence is
# always: stop/accept-death -> sweep -> relaunch.
#
# Run BEFORE: warm-slots, any drain relaunch after an unclean stop.
# (Lesson log: orphaned worker subtrees hold slot dirs by CWD, invisible
# to command-line matching; the dead-parent test is what finds them.)

$all = Get-CimInstance Win32_Process
$byid = $all | Group-Object ProcessId -AsHashTable -AsString
$sus = $all | Where-Object {
    ($_.Name -match '^(git|python|uv|bash|sh|cmd|conhost|pnpm|bun|cargo|go)') -or
    ($_.Name -match 'claude|node' -and $_.CommandLine -match 'dangerously-skip-permissions')
}
$orphans = foreach ($p in $sus) {
    if (-not $byid.ContainsKey("$($p.ParentProcessId)")) { $p }
}
$killed = 0
foreach ($o in $orphans) {
    taskkill /F /T /PID $o.ProcessId 2>&1 | Out-Null
    $killed++
}
Write-Output "$killed orphan tree(s) killed"
