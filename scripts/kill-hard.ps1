# kill-hard.ps1 — the HARD stop. Kills every harness/drain process tree and
# verifies nothing survived.
#
# Why this exists: kill-orphans.ps1 only sweeps processes whose PARENT is
# already dead. After E13's pause, workers with live parents survived ~40
# minutes and completed 32 more runs; later sweeps killed shell trees while
# claude.exe children kept running. This script instead:
#   1. Finds ROOTS: any process whose command line matches the harness
#      signature (harness run/drain2/run-skills/run-judge, the drain shell
#      scripts, uv-run-harness, or claude/node carrying
#      --dangerously-skip-permissions).
#   2. Walks the FULL tree below every root via Win32_Process
#      ParentProcessId recursion (bash -> uv -> python -> claude -> node),
#      guarding against PID reuse with CreationDate ordering.
#   3. Kills leaf-first, then re-queries and ASSERTS no process matching
#      the signature survives. Exit 0 only on a verified-clean sweep;
#      exit 1 if survivors remain.
#
# The current PowerShell process and its ancestors are excluded, so running
# this from a terminal (or an agent session) never kills its own tree.
#
# Use whenever a drain must be dead NOW: before warm-slots, before a
# relaunch, after a pause. Unlike kill-orphans.ps1 this WILL kill a live
# drain — that is the point.

$ErrorActionPreference = 'Continue'

$signature = 'dangerously-skip-permissions|harness(\.exe)?["'']?\s+(run|drain2|run-skills|run-judge|smoke|warm-slots)|coding-drain\.sh|skills-drain\.sh|skills-loop\.sh|judge-drain|lh-probe\.sh|pilot-loop\.sh|sensitivity-batch\.sh|uv(\.exe)?["'']?\s+run\s+(python\s+-c\s+.*harness|harness)'

function Get-Snapshot {
    Get-CimInstance Win32_Process |
        Select-Object ProcessId, ParentProcessId, Name, CommandLine, CreationDate
}

function Get-MatchingRoots($all) {
    $all | Where-Object { $_.CommandLine -match $signature }
}

# Self-protection: never kill this process or anything above it.
$protected = @{}
$byId = @{}
$all = Get-Snapshot
foreach ($p in $all) { $byId[[uint32]$p.ProcessId] = $p }
$cursor = [uint32]$PID
while ($byId.ContainsKey($cursor) -and -not $protected.ContainsKey($cursor)) {
    $protected[$cursor] = $true
    $cursor = [uint32]$byId[$cursor].ParentProcessId
}

# Build the child map (PID-reuse guard: a real child was created after its
# parent; a recycled ParentProcessId pointing at a younger process is noise).
$children = @{}
foreach ($p in $all) {
    $ppid = [uint32]$p.ParentProcessId
    $parent = $byId[$ppid]
    if ($null -ne $parent -and
        $null -ne $parent.CreationDate -and
        $null -ne $p.CreationDate -and
        $parent.CreationDate -le $p.CreationDate) {
        if (-not $children.ContainsKey($ppid)) { $children[$ppid] = @() }
        $children[$ppid] += [uint32]$p.ProcessId
    }
}

# Collect the full tree under every signature root, depth-tagged.
$roots = Get-MatchingRoots $all
$depth = @{}
$queue = New-Object System.Collections.Queue
foreach ($r in $roots) {
    $rpid = [uint32]$r.ProcessId
    if (-not $depth.ContainsKey($rpid)) {
        $depth[$rpid] = 0
        $queue.Enqueue($rpid)
    }
}
while ($queue.Count -gt 0) {
    $cur = $queue.Dequeue()
    if ($children.ContainsKey($cur)) {
        foreach ($kid in $children[$cur]) {
            if (-not $depth.ContainsKey($kid)) {
                $depth[$kid] = $depth[$cur] + 1
                $queue.Enqueue($kid)
            }
        }
    }
}

$targets = $depth.Keys |
    Where-Object { -not $protected.ContainsKey($_) } |
    Sort-Object { $depth[$_] } -Descending   # leaf-first

if ($targets.Count -eq 0) {
    Write-Output "nothing to kill: no process matches the harness signature"
    exit 0
}

$killed = @()
foreach ($tpid in $targets) {
    $proc = $byId[$tpid]
    taskkill /F /PID $tpid 2>&1 | Out-Null
    $killed += "[depth $($depth[$tpid])] pid=$tpid $($proc.Name) :: $($proc.CommandLine)"
}

Write-Output "killed $($killed.Count) process(es), leaf-first:"
$killed | ForEach-Object { Write-Output "  $_" }

# Verify: after the sweep, NOTHING matching the signature may survive.
Start-Sleep -Seconds 2
$after = Get-Snapshot
$survivors = Get-MatchingRoots $after | Where-Object {
    -not $protected.ContainsKey([uint32]$_.ProcessId)
}
if ($survivors) {
    Write-Output "SWEEP FAILED: $(@($survivors).Count) survivor(s) still match the harness signature:"
    $survivors | ForEach-Object {
        Write-Output "  pid=$($_.ProcessId) $($_.Name) :: $($_.CommandLine)"
    }
    exit 1
}
Write-Output "verified clean: no harness-signature process survives"
exit 0
