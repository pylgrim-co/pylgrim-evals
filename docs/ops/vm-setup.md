# Harness VM setup guide (Hetzner)

Stands up the always-on Linux box that runs the eval drains — the
execution environment ratified for E-coord (and the Wave-2 default),
2026-08-01. Motivation: the local Windows host lost four drains in two
weeks to sleep/wake and session deaths, and E-coord's budget
(~3,300-4,200 CLI completions) is a 6-10+ week calendar exposure locally.
The VM adds uptime, not subscription capacity — see §10 before assuming
it makes anything faster.

Follow top to bottom. Every step ends with a `verify:` command; do not
continue past a failing verify. Steps assume you are `sam` on the box
after §2. Versions installed here get RECORDED (§8) and become pinned
harness config at the E-coord freeze — don't upgrade them casually
afterward.

## 1. Provision

In the [Hetzner Cloud console](https://console.hetzner.com): New project
`pylgrim-evals` → Add Server:

- **Location:** Falkenstein (`fsn1`) or Nuremberg (`nbg1`), Germany —
  CPX32 is not offered in the US locations (2026-08). EU is fine: the
  drain's traffic is CLI→API and run-duration-bound, so transatlantic
  latency is noise; SSH lag is absorbed by tmux/mosh; no
  jurisdiction-sensitive data. Only if you insist on US: CPX42 at
  ~2× the price.
- **Image:** Ubuntu 24.04 LTS.
- **Type:** Shared vCPU (AMD) **CPX32** — 4 vCPU, 8 GB RAM, 160 GB
  NVMe, US$46.19/mo (US-location pricing, 2026-08). Sizing: E-coord
  episodes run strictly serially (review finding O9), so at most one
  test-suite build is live at a time — 4 vCPU/8 GB covers it, and
  160 GB holds repos + worktree slots + shared build caches (~60-100 GB
  steady state). NOT CPX22: 4 GB OOMs on nushell's cargo builds. If a
  Wave-2 parallel drain (5 single-shot workers) later wants more cores,
  rescale up to CPX42 in place — choose "vCPU and RAM only" so the disk
  doesn't grow and the rescale stays reversible.
- **SSH key:** add your public key at create time (`ssh-keygen -t
  ed25519` locally if you don't have one). Do NOT enable password login.
- Skip volumes/backups for now (backups are ~20%/mo; §7's rsync covers
  the data that matters — revisit if the VM becomes the only copy of
  anything).

verify (local machine):

    ssh root@<server-ip> 'lsb_release -ds && nproc && df -h /'
    # expect: Ubuntu 24.04.x LTS, 8, ~226G available

## 2. First login and hardening

As root:

    adduser sam            # pick a strong password (sudo prompt only)
    usermod -aG sudo sam
    rsync --archive --chown=sam:sam ~/.ssh /home/sam
    ufw allow OpenSSH && ufw --force enable
    apt update && apt install -y unattended-upgrades
    dpkg-reconfigure -plow unattended-upgrades   # choose Yes

Then edit `/etc/ssh/sshd_config`: set `PasswordAuthentication no` and
`PermitRootLogin no`, then `systemctl restart ssh`.

**Recommended — Tailscale** (reach the box from any of your machines
with no open ports; makes §7's rsync trivial):

    curl -fsSL https://tailscale.com/install.sh | sh
    tailscale up    # authenticate in the browser link it prints

verify (local machine — new terminal, don't close the root session
until this passes):

    ssh sam@<server-ip> 'sudo -v && echo OK'     # key login as sam, sudo works
    ssh root@<server-ip> 'echo should-fail'      # expect: Permission denied

## 3. Toolchains

Matched to the corpus repos' test suites (node: zustand/zod/eslint/
prettier/sql-formatter/rich? — check tasks/ for the current corpus;
rust: nushell; go: hugo; python: click/rich + the harness itself).

    # node LTS + pnpm (corepack)
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt install -y nodejs build-essential
    sudo corepack enable

    # rust (pinned toolchain — record the version in §8)
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"

    # go + hugo (extended)
    sudo apt install -y golang-go
    sudo snap install hugo

    # python + uv (harness runtime)
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env"

    # shared build caches — pinned harness config (review finding O4):
    # merged-tree checkouts must not cold-build
    mkdir -p ~/.cache/pylgrim-build/cargo-target
    echo 'export CARGO_TARGET_DIR="$HOME/.cache/pylgrim-build/cargo-target"' >> ~/.bashrc

verify:

    node -v && pnpm -v && cargo -V && go version && hugo version && uv -V
    # all six print versions; record them now in the §8 table

## 4. Claude Code

    curl -fsSL https://claude.ai/install.sh | bash

Auth on a headless box, subscription (not API key). Preferred: generate
a long-lived token on your LOCAL machine, where a browser exists:

    # local machine
    claude setup-token          # browser OAuth; prints a token

    # VM — persist it for interactive AND systemd use (§6 reads this file)
    echo 'export CLAUDE_CODE_OAUTH_TOKEN=<token>' >> ~/.claude-token
    echo 'source ~/.claude-token' >> ~/.bashrc && source ~/.bashrc

(Fallback: run `claude` in the SSH session and complete the `/login`
device flow by opening the printed URL locally.)

Pin the CLI version: the harness records it per run; do not auto-update
mid-study. Check the installed version now and record it in §8.

verify:

    claude --version
    claude -p 'reply with exactly: VM-OK' --max-turns 1
    # expect: VM-OK (this confirms token + subscription routing)

## 5. Repos

    # deploy key for GitHub
    ssh-keygen -t ed25519 -C "pylgrim-vm" -f ~/.ssh/github -N ""
    cat ~/.ssh/github.pub   # add at github.com → Settings → SSH keys
    printf 'Host github.com\n  IdentityFile ~/.ssh/github\n' >> ~/.ssh/config

    git config --global user.name  "samuelheal"
    git config --global user.email "samuel.j.heal@gmail.com"

    git clone git@github.com:pylgrim-co/pylgrim-evals.git ~/pylgrim-evals
    cd ~/pylgrim-evals/harness && uv sync

Corpus repos: the harness creates and pins its own repo mirrors/slots on
first claim (slots/ off bare clones at pinned SHAs) — you do not clone
them by hand. The §9 smoke test primes them.

verify:

    cd ~/pylgrim-evals/harness && uv run harness --help | head -5
    ssh -T git@github.com   # expect the "successfully authenticated" banner

## 6. Drain service (systemd)

`/etc/systemd/system/pylgrim-drain.service`:

    [Unit]
    Description=pylgrim-evals drain2
    After=network-online.target
    Wants=network-online.target

    [Service]
    User=sam
    WorkingDirectory=/home/sam/pylgrim-evals/harness
    EnvironmentFile=/home/sam/.claude-token-env
    Environment=CARGO_TARGET_DIR=/home/sam/.cache/pylgrim-build/cargo-target
    ExecStart=/home/sam/.local/bin/uv run harness drain2 --root .. --workers 5
    Restart=always
    RestartSec=30
    KillMode=control-group

    [Install]
    WantedBy=multi-user.target

`EnvironmentFile` wants `KEY=value` lines (no `export`):

    grep -oP 'CLAUDE_CODE_OAUTH_TOKEN=\S+' ~/.claude-token > ~/.claude-token-env

Operating it — these replace every babysitting pattern from the Windows
era:

    sudo systemctl enable --now pylgrim-drain    # start + start-on-boot
    sudo systemctl stop pylgrim-drain            # THE pause (kills the whole
                                                 # cgroup; nothing survives)
    journalctl -u pylgrim-drain -f               # live log

drain2's heartbeat reclaim (10 min stale threshold) means a crashed or
OOM-killed worker's claims are re-absorbed automatically on restart —
no manual stale resets, ever. Liveness alarm, checked every 10 min
(`pylgrim-drain-watch.timer` + `.service`, `Type=oneshot`):

    ExecStart=/bin/bash -c 'test -z "$(sqlite3 /home/sam/pylgrim-evals/results/runs.db \
      "SELECT 1 WHERE (SELECT COUNT(*) FROM runs WHERE status=\"running\" \
       AND heartbeat_at < datetime(\"now\",\"-20 minutes\")) > 0")" \
      || systemctl restart pylgrim-drain'

verify (safe with an empty queue — drain2 idles):

    sudo systemctl start pylgrim-drain && sleep 10
    systemctl is-active pylgrim-drain            # expect: active
    journalctl -u pylgrim-drain -n 5 --no-pager  # expect startup banner, no traceback
    sudo systemctl stop pylgrim-drain && pgrep -u sam -f 'harness|claude' ; echo "exit=$?"
    # expect: no PIDs, exit=1  (the cgroup kill IS the hard stop)

## 7. Results and backup

The live `results/runs.db` and artifacts live on the VM. Rules:

- **Analysis reads a synced copy.** Never point local analysis at the
  live DB over the network, and never write the live DB remotely; the
  drain owns it.
- Pull a snapshot to your machine (Tailscale hostname or IP), from
  local:

      rsync -az --info=progress2 sam@<vm>:pylgrim-evals/results/ \
            C:/Dev/pylgrim-master/pylgrim-evals/results-vm/

- Nightly safety copy on the VM itself (survives fat-fingered deletes,
  not disk loss — Hetzner snapshots cover that if wanted):

      (crontab -l 2>/dev/null; echo '17 3 * * * sqlite3 ~/pylgrim-evals/results/runs.db ".backup ~/runs-backup.db"') | crontab -

verify (local): the rsync completes and `results-vm/runs.db` opens in
sqlite3 with the expected row counts.

## 8. Environment pinning record

Record NOW and again at every freeze (this table is what the prereg's
pinning list cites). Keep it in this file, dated:

| item | value (2026-08-__) |
|---|---|
| VM | Hetzner CPX41, hil, Ubuntu 24.04.x |
| kernel | `uname -r` |
| git | `git --version` (C1 depends on merge-tree semantics) |
| Claude Code CLI | `claude --version` |
| node / pnpm | |
| rustc / cargo | |
| go / hugo | |
| python / uv | |
| build caches | CARGO_TARGET_DIR=~/.cache/pylgrim-build/cargo-target |

verify: every row filled; the same command list re-run at freeze diffs
clean.

## 9. Smoke test (end-to-end)

From `~/pylgrim-evals/harness`, schedule a tiny throwaway batch (2 runs
of a light card, e.g. zod-t01, on haiku, in a rep range that cannot
collide — check the DB max first as the append scripts do), then:

    sudo systemctl start pylgrim-drain
    watch -n 30 'sqlite3 ../results/runs.db "SELECT status, COUNT(*) FROM runs GROUP BY status"'

Expect: both runs claim (heartbeats advancing), complete within ~10 min
each, artifacts land under `results/runs/<run_id>/`. Then one judge:

    uv run harness plan-judge --root ..
    uv run harness run-judge --root .. --batch 2

Expect: verdicts rows `done` with structured output (no "unparseable").
Delete/ignore the smoke rows per the append script's collision-guard
conventions before any real study appends.

verify: the two coding runs `done`, judge `done`, zero errors, and the
corpus mirror for the smoke repo exists under the harness's slots dir.

## 10. Cost and contention

| item | monthly |
|---|---|
| CPX32 | US$46.19 |
| Tailscale (personal) | $0 |
| **total** | **~US$46** (CPX42 rescale for Wave-2 parallel weeks: US$90.19) |

What the VM buys: uptime (no sleep/wake deaths, no session-tied drains,
`systemctl stop` as a verified pause) and a Linux environment that
removes the Windows-host caveat from future preregs. What it does NOT
buy: throughput. The subscription cap is account-level; five workers
here consume the same Max capacity as five workers locally, in
contention with your interactive sessions. If contention bites:

1. **Off-hours windows** — free: run the drain only while you sleep
   (`systemd` timer: `systemctl start` at 23:00, `stop` at 08:00 your
   time).
2. **Second subscription** dedicated to the harness (~$100-200/mo) —
   full isolation, still flat-rate.
3. **API billing** — full isolation and no cap, but waves become real
   money (W1.5-scale ≈ $450 at observed run costs; E-coord episodes are
   multi-turn and land higher per episode).

Decide only when contention actually hurts; the guide's default (shared
subscription, drain runs whenever) matches how the program has run to
date.

## Appendix: non-Hetzner providers

Any Ubuntu 24.04 box with ≥8 vCPU / 16 GB / 200 GB and a public IP or
Tailscale works identically from §2 onward — §1 is the only
Hetzner-specific section. Equivalents: AWS `t3a.2xlarge` + 200 GB gp3
(~US$70-90/mo), GCP `e2-standard-8` (~US$60-80/mo, sustained-use).
