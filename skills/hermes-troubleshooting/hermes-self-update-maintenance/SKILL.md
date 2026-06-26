---
name: hermes-self-update-maintenance
description: Maintain a long-lived git-installed Hermes Agent safely — keep it patched without breaking sessions, cron jobs, profiles, or memory. Covers the three update lanes (tagged release, main HEAD, full reinstall), the wait-one-tag pattern for fresh releases, version pinning, rollback, and how to wire a passive weekly check that reports updates without auto-applying them.
version: 1.0.0
author: Hermes Agent
created_by: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, maintenance, self-update, git, cron, safety]
---

# Hermes Self-Update Maintenance

When Hermes is installed from a git clone (the default for long-lived household / workbench installs), the user owns version management. There is no auto-update — and that's the right design, because a silent update to a running Hermes can break cron jobs mid-firing, change skill loading behavior, deprecate config keys, or shift tool signatures under sessions that are in flight. This skill is the operational playbook for keeping a git-installed Hermes patched safely without breaking what's already working.

For *how to USE* Hermes (config, providers, plugins, voice, tools, etc.) load the bundled `hermes-agent` skill. This skill is about *keeping it maintained* — a different concern, run on a different cadence.

## When to use

Trigger on:
- "Update Hermes" / "what's the safe way to upgrade?"
- "Is there a newer version?" / "am I behind on Hermes?"
- "Set up automatic Hermes updates"
- A new release is mentioned (Discord, release feed) and the user asks whether to apply it
- After a breaking change is reported and you need to roll back

## Three update lanes, ranked by safety

| Lane | Command | Safety | When to use |
|---|---|---|---|
| 🟢 **Tagged release** | `cd ~/.hermes/hermes-agent && git fetch --tags && git checkout vX.Y.Z && hermes doctor` | Safest. Tags are intentional release points, version-bumped, packaging-verified. | Default lane for any long-lived install. |
| 🟡 **`main` HEAD** | `cd ~/.hermes/hermes-agent && git pull && hermes doctor` | Middle. Bleeding edge — gets fixes faster, but also gets WIP commits that haven't been packaged or smoke-tested. | Only when the user explicitly wants an unreleased fix or is helping develop. |
| 🔴 **Full reinstall** | `curl -fsLS https://hermes-agent.nousresearch.com/install.sh | bash` | Worst for upgrades. Reinstall scripts are designed for first-time setup; running them on a configured install can clobber `~/.hermes/.env`, regenerate config defaults, or re-link plugins. | Use ONLY for first install, or after a corrupted install you can't recover. Back up `~/.hermes/.env`, `~/.hermes/config.yaml`, `~/.hermes/memories/`, and `~/.hermes/skills/` first. |

**Default recommendation**: tagged release lane, always. The other two are escape hatches.

## Where you run the update from matters (the gateway self-stop trap)

**The single most disruptive failure mode for a long-lived gateway install: triggering a gateway-stopping update from inside a session that is *delivered through that same gateway*.** When Hermes runs as a messaging gateway (Discord/Telegram/etc.), your tool calls are executed by the gateway process. `hermes update` stops the gateway as step one — which kills the very process delivering your conversation. The update dies mid-flight (or finishes blind, with no way to report back), and the session tears down with a "gateway shutdown" interrupt. You cannot saw off the branch you're sitting on.

Three safe ways to drive the update instead:

| Driver | How | When |
|---|---|---|
| 🟢 **Decoupled oneshot systemd unit** | A `hermes-update.service` (`Type=oneshot`) that stops the gateway, updates, and restarts it — running as its OWN unit so the gateway bounce can't kill it. Trigger with `systemctl --user start hermes-update.service`. Known-good unit + script in `templates/` below. | Best for a systemd-managed install. Survives the gateway dying. |
| 🟢 **User runs it from a terminal / SSH** | Hand the user a copy-paste block; they run `hermes update` from a shell that is NOT the gateway. | When the user is at the machine. Simplest, most observable. |
| 🟡 **`terminal(background=True)` + nohup/setsid** | Detach the updater from the tool call. Fragile — the bg process can still be reaped when the session tears down at the stop step. | Last resort; the oneshot unit is strictly better. |

**Never** call `hermes update`, `systemctl stop hermes-gateway`, or `hermes gateway stop` in the foreground of a gateway-delivered session and expect to narrate the result. You lose contact at the stop step. If the user is sitting at the machine, prefer handing them the terminal block — it's the most observable path for a big multi-hundred-commit jump.

### Verify the gateway IS a systemd unit before assuming it isn't

On a long-lived install, `hermes gateway install` has almost certainly registered `hermes-gateway.service` as a **systemd user unit** with linger enabled — it is NOT a bare `nohup` process, even though `ps` shows a plain `python -m hermes_cli.main gateway run` line. (Diagnosing it as "not a systemd unit" because `systemctl stop` appeared to hang is a documented misread — see the `TimeoutStopSec` pitfall below for what actually hangs.) Check before reasoning about how to stop it:

```bash
systemctl --user list-unit-files | grep -i hermes      # units present?
systemctl --user status hermes-gateway --no-pager        # tracked PID, state
loginctl show-user "$USER" | grep -i linger              # Linger=yes → survives logout
```

Each profile that runs a gateway gets its OWN unit, e.g. `hermes-gateway-local-intimate.service`. Don't assume "default only" — enumerate them.

### The `TimeoutStopSec=210` hang

The unit shipped by `hermes gateway install` sets `TimeoutStopSec=210`. A `--replace` gateway that doesn't exit promptly on SIGTERM makes `systemctl --user stop hermes-gateway` **block for up to 3.5 minutes** before systemd force-kills it — long enough that a wrapping script looks hung and an enclosing session times out. THIS is what masquerades as "systemctl can't find the unit." Lower it so a stop can't stall an update:

```ini
# in ~/.config/systemd/user/hermes-gateway.service, [Service] section
TimeoutStopSec=30
```
Then `systemctl --user daemon-reload`. Verify with `systemctl --user show hermes-gateway -p TimeoutStopUSec` (expect `TimeoutStopUSec=30s`). Apply to every per-profile gateway unit, not just default.

## The wait-one-tag pattern (read before applying any fresh release)

When a new tag drops, **wait 24-48 hours before applying it** — unless the release notes explicitly fix a problem affecting this install.

Why: Hermes releases sometimes ship `.X` followed within hours by `.X.1` or `.X.2` as packaging / hotfix patches. If you see two tags drop the same day:
- `v2026.5.29` — initial release
- `v2026.5.29.2` — packaging fix (e.g. missing `plugin.yaml` in wheel/sdist) or one-line bug fix

The `.N` suffix is almost always the hotfix for what `.0` broke. Skipping to the highest available tag is virtually always the right move. The 24-hour wait also catches social signal — if a tag breaks something for someone, they post about it within a day, and you can hold off.

## Detecting how far behind you are

```bash
cd ~/.hermes/hermes-agent
git fetch --tags --quiet
current=$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)
latest=$(git tag -l 'v*' | sort -V | tail -1)
echo "current: $current"
echo "latest:  $latest"
[ "$current" = "$latest" ] && echo "✓ up to date" || {
  behind=$(git rev-list --count "$current..$latest" 2>/dev/null)
  echo "→ $behind commits behind $latest"
  git log --oneline "$current..$latest"
}
```

This is the core of the weekly check script — see `scripts/hermes_update_check.sh` for a production-ready version that exits silently when current and prints a summary + safe-checkout one-liner + rollback line when not.

## Wiring a weekly passive check (cron, no auto-apply)

The right shape is: **check weekly, report deltas, never auto-apply**. The user reads the report, decides whether to apply, and runs the checkout themselves. This preserves agency and avoids "Hermes silently updated and broke my cron at 3 AM" scenarios.

Use a `no_agent` cron job with the bundled check script — no LLM calls, no tokens, just the script's stdout delivered verbatim. The script must exit silently (empty stdout) when no update is available so the user isn't pinged on the 50 weeks/year that nothing changed.

```python
cronjob(action='create',
        name='hermes-update-check-weekly',
        schedule='0 9 * * 1',           # Monday 9 AM
        no_agent=True,
        script='hermes_update_check.sh', # bare filename — see pitfall below
        deliver='origin',
        repeat=0)  # forever
```

**Cron `script` field pitfall**: the `script` field requires a **bare filename relative to `~/.hermes/scripts/`**, NOT an absolute path. Passing `/home/<user>/.hermes/scripts/foo.sh` raises a validation error at create time. Put the script at `~/.hermes/scripts/<name>.sh`, mark executable, pass just the filename.

## Updating a gateway-backed install without self-deadlocking

If Hermes runs as a **gateway** (Discord/Telegram/etc. via `hermes-gateway.service`),
the update has a trap that bit hard on 2026-06-06: **you cannot reliably run
`hermes update` from inside a tool call that is itself delivered through that
gateway.** `hermes update` stops the gateway → the gateway is the transport carrying
your session → the session dies mid-update → you go blind to whether it finished. In
that session the update was attempted three times from inside the Discord-delivered
agent loop and each attempt was torn down at the gateway-stop step.

Two compounding failure modes:

1. **`systemctl --user stop hermes-gateway` blocks for `TimeoutStopSec`.** The shipped
   unit defaulted to `TimeoutStopSec=210` (3.5 min). A `--replace` gateway that doesn't
   exit promptly on SIGTERM makes the stop hang for the full timeout — long enough to
   look wedged and to outlast the calling session. **Fix: lower to `TimeoutStopSec=30`**
   in the unit; clean shutdown is fast, and after 30s systemd escalates to SIGKILL.
2. **An updater launched as a child of the gateway-delivered session dies with the
   gateway.** `nohup`/`&` from inside the session is not enough — the whole process
   group can go down with the gateway bounce.

### The fix: a decoupled `Type=oneshot` systemd unit

Run the update as its **own** systemd user unit so it outlives the gateway bounce. The
unit invokes a script that does: backup → stop gateway → `git fetch` + checkout target
tag → `uv pip install -e .` → `config migrate` → `doctor` → restart gateway. Because
the unit is independent of the gateway, killing the gateway cannot kill the updater.

```bash
# Pin the target tag, then fire the oneshot:
systemctl --user set-environment HERMES_UPDATE_TARGET=v2026.6.5
systemctl --user start hermes-update.service
journalctl --user -u hermes-update.service -f   # watch it run
```

Ready-to-adapt artifacts ship with this skill:
- `templates/hermes-update.service` — the oneshot unit (adjust the hardcoded paths).
- `scripts/hermes_self_update.sh` — the update script it runs (backup + decoupled
  stop/checkout/reinstall/restart, logs to `~/.hermes/logs/self-update-*.log`, prints
  a rollback line). Verified end-to-end on the v0.15.2 → v0.16.0 (953-commit) jump.

### When the agent IS the gateway session

If you (the agent) are driving through the very gateway you must restart, do NOT
`systemctl stop` it inline and keep issuing tool calls — those calls travel through the
dying gateway. Instead either: (a) **hand the user the one-liner**
(`systemctl --user start hermes-update.service`) to run from a terminal, or (b) **fire
the oneshot and expect your session to drop**, then reconnect after the gateway
restarts and verify `hermes version`. The oneshot completes detached either way.

## Rollback

Every update report should include the rollback line for the version you're moving FROM. The user keeps the previous tag in their notes (or your skill report) so reverting is one line:

```bash
cd ~/.hermes/hermes-agent && git checkout <previous-tag> && hermes doctor
```

If `hermes doctor` reports failures after an update, roll back FIRST, then investigate. Don't try to debug a broken install while it's the only Hermes you have — restore the working version, then reproduce the failure on a side checkout.

## After updating: verify, don't assume

```bash
hermes doctor                      # plugin/config/provider sanity
hermes version                     # confirms the upgrade landed
cronjob list                       # confirms cron jobs survived schema changes
# poke a representative skill load:
hermes skills list | head
```

If `hermes doctor` reports new warnings that weren't there before, READ them — sometimes a tag adds a new required config key that defaults gracefully but warns about the missing entry. Acknowledge in `config.yaml` rather than ignoring the warning forever.

## What NOT to do

- ❌ **Don't `git pull` on `main` casually.** Main HEAD includes WIP commits. Use tagged releases unless you're actively developing.
- ❌ **Don't re-run `install.sh` to update.** It's a setup script, not an updater. It will clobber config.
- ❌ **Don't auto-apply updates via cron.** Always report-only. The user decides when to take the downtime.
- ❌ **Don't update mid-session while cron jobs are scheduled to fire imminently.** Either wait for the cron window to close, or pause the jobs (`cronjob action='pause'`) during the upgrade.
- **Don't update Hermes and other big systems (HA, Docker daemon, kernel) in the same window.** If something breaks, you need a clean blame surface.
- ❌ **Don't run `hermes update` inline from a session delivered through the gateway you're about to restart.** It saws off the branch you're sitting on. Use the decoupled oneshot unit (see "Updating a gateway-backed install without self-deadlocking").
- ❌ **Don't leave `TimeoutStopSec=210` on the gateway unit.** A slow SIGTERM exit makes `systemctl stop` hang 3.5 min and masquerade as a wedge. Lower to 30s.

## Updating from inside a gateway-delivered session (the self-decapitation hazard)

The single most expensive failure when "just run the update" arrives over a messaging
gateway (Discord/Telegram/etc.): the update sequence stops the gateway, but the tool
call issuing that stop is **itself delivered through that same gateway**. Killing the
gateway kills the caller mid-update — the run is orphaned, the session is torn down,
and you return to a half-known state. Observed biting THREE times in one session
before the decoupled fix landed.

Two compounding traps:

1. **`systemctl --user stop hermes-gateway` can hang for the full `TimeoutStopSec`.**
   A `--replace` gateway that doesn't exit promptly on SIGTERM makes the stop block
   until systemd force-kills it. A unit shipping `TimeoutStopSec=210` is a 3.5-minute
   hang that outlives the session. **Lower it to ~30s** (`TimeoutStopSec=30`).
   FIRST verify the unit actually EXISTS before concluding "the gateway isn't a systemd
   service" — it usually IS a proper enabled unit; the hang is the stop timeout, not a
   missing unit. (Don't assert "not a systemd unit" without `systemctl --user status`.)
2. **Backgrounding inside the gateway's process tree doesn't save you** — a `nohup`
   updater that's still a descendant of the gateway dies when the gateway is torn down.

### The fix: a decoupled one-shot systemd unit

Run the update as its **own** `Type=oneshot` systemd unit, independent of the gateway
lifecycle, so stopping the gateway can't kill the updater. The unit's `ExecStart` is a
wrapper script that: backup config/secrets/memories → stop gateway → `git fetch` +
checkout target tag → reinstall deps (`uv pip install -e .`) → `config migrate` →
`doctor` → restart gateway. Trigger with `systemctl --user start hermes-update.service`
and it outlives the gateway bounce. Pin the target via
`systemctl --user set-environment HERMES_UPDATE_TARGET=<tag>` (read by the wrapper).
Give the unit a generous `TimeoutStartSec` (e.g. 1800) for big dep reinstalls. Worked
example (unit + wrapper): `references/decoupled-self-update-via-systemd.md`.

**Lowest-ceremony alternative when a human is present:** have them run the update from
a plain terminal or SSH session — NOT through the gateway. A shell that isn't a child
of the gateway survives the gateway stop trivially. Reach for the decoupled unit when
it must be hands-off / repeatable.

## Pitfalls

### Contributing a fix upstream FROM a tag-pinned install (build against main, not your HEAD)

A long-lived install sits on a **pinned release tag** (e.g. v0.16.0), often hundreds of
commits behind `main`. When you write a hotfix locally and want to PR it upstream, do
NOT branch off your pinned HEAD and PR against `main` — `conversation_loop.py` and other
hot files get heavily refactored between tags (observed 2026-06-08: 387 commits behind,
the target file was +157/-827 vs the pinned copy). A PR off the stale base either won't
merge or reintroduces hundreds of deleted lines.

The clean workflow that keeps your **running install tree untouched** (its uncommitted
local hotfix stays put) while you build the PR against current main:

```bash
cd ~/.hermes/hermes-agent
git fetch origin main --quiet
# disposable worktree on fresh main — does NOT disturb your detached pinned HEAD
git worktree add -b fix/<class-level-name> /tmp/hermes-pr origin/main
# re-apply the fix in the worktree against main's CURRENT structure (it may differ:
# e.g. retry guards moved into agent/turn_retry_state.py::TurnRetryState as a dataclass,
# so a bare local var on the old tag becomes a new dataclass field + a contract-test update)
# ... edit, then run the affected suites with the shared venv ...
~/.hermes/hermes-agent/venv/bin/python -m pytest <affected tests> -q
git -C /tmp/hermes-pr add -A && git -C /tmp/hermes-pr commit -m "fix(scope): ..."
git -C /tmp/hermes-pr push -u fork HEAD          # fork = your own GitHub remote
gh pr create --repo NousResearch/hermes-agent --base main \
  --head <your-gh-user>:fix/<class-level-name> --body-file /tmp/body.md
git worktree remove /tmp/hermes-pr --force && git worktree prune
```

Gotchas that bit and are worth pre-empting:
- **`origin` is NousResearch (read-only), `fork` is your own GitHub user.** Push to `fork`,
  PR `--head <your-gh-user>:<branch>`. `gh auth` token has `repo`+`workflow` scope.
- **Main may carry a contract/shape test** that pins the exact field set of a refactored
  structure (e.g. `tests/agent/test_turn_retry_state.py::test_field_set_matches_contract`).
  Adding a field fails it until you update `EXPECTED_FIELDS` too — run the owning test,
  let it catch you, fix the contract in the same commit.
- **`config.yaml` and some core files are `patch`-tool protected** — but worktree source
  files under the repo are not; edit them normally.
- The worktree shares the install's venv via the `run_tests.sh` `$HOME/.hermes/hermes-agent/venv`
  probe, so tests run without a second venv.
- **This is a BEHAVIOR change → your person gates it. Open the PR, never self-merge.** Verify
  it landed with `gh pr view <N> --json state,baseRefName,mergeable` — don't trust the
  create URL alone.

### Profile-aware updates

The headline failure mode — see "Where you run the update from matters" above. You cannot stop the gateway from a tool call delivered through that gateway and live to report the result. Use the decoupled oneshot unit (`templates/hermes-update.service` + `templates/hermes_self_update.sh`) or hand the update to the user's terminal.

### Misdiagnosing the `systemctl stop` hang as "no unit"

A `systemctl --user stop hermes-gateway` that appears to hang is almost never "the unit doesn't exist" — it's the **210-second `TimeoutStopSec`** waiting on a `--replace` gateway that's slow to exit on SIGTERM. Verify the unit exists (`systemctl --user list-unit-files | grep hermes`) before concluding anything about the supervision model. Fix is lowering `TimeoutStopSec`, not reinventing the service.

### The editable-install reinstall step (don't skip it on a big jump)

The git-installed Hermes venv is a **uv-backed editable install** (`uv pip install -e .`, an `__editable___hermes_agent_*_finder.install()` line in the venv `.pth`). A version jump that adds new top-level modules (e.g. `hermes_bootstrap`) needs the editable install re-run so the `.pth` finder learns the new module set — a bare `git checkout` alone can leave `hermes` crashing on import with `ModuleNotFoundError` until deps are reinstalled. `hermes update` does this for you; if you script the update by hand, replicate it: `VIRTUAL_ENV=<repo>/venv uv pip install -e <repo>` (fall back to `<repo>/venv/bin/python -m pip install -e <repo>` when uv is absent). The codebase guards its own entrypoint against this half-updated state, but don't rely on the guard — run the reinstall.

Hermes profiles share the same install but have their own `~/.hermes/profiles/<name>/skills/`, `cron/`, `memories/`. The update affects the binary/code — it does NOT migrate per-profile state. If a release adds a new schema for skill frontmatter or cron storage, you may need to re-run a migration command per profile. Check release notes; `hermes doctor` will usually flag this.

### Plugin compatibility

Tag bumps can change plugin loading. After a major version jump (e.g. `v2026.5.x → v2026.6.x`) verify any installed plugins (especially hub-installed ones via `hermes plugins list`) still load cleanly. A plugin pinned to an older API surface will fail loud — patch by either updating the plugin or pinning Hermes back to the last compatible tag while the plugin author catches up.

### Don't bundle config changes into the update commit

If you have local edits in `~/.hermes/hermes-agent/` (you shouldn't, but it happens for hotfix experiments), `git checkout vX.Y.Z` will refuse or silently lose them. `git stash` before checkout, inspect after.

### The "weekly check fires but reports nothing" sanity

A `no_agent` cron that exits silently when there's nothing to say means **the user will never see it on quiet weeks**. That's correct (the whole point of the watchdog pattern), but if the user later asks "is the update check actually running?" you need a way to prove it. Two approaches:
1. Have the script also write a `~/.hermes/state/hermes_update_last_check` timestamp file every run. User can `stat` it.
2. Once a quarter (or on demand) call `cronjob action='run' job_id=...` manually to force a fire and confirm the channel works.

Don't add periodic "everything's fine" pings to compensate — they train the user to ignore the channel.

## Verification checklist after any update

- [ ] `hermes version` shows the new tag
- [ ] `hermes doctor` exits clean (or only warns about things you've documented)
- [ ] `cronjob list` shows all expected jobs intact
- [ ] One representative cron job runs successfully (`cronjob action='run'`)
- [ ] A test session loads + responds normally
- [ ] At least one skill loads via `skill_view`
- [ ] Rollback command is recorded somewhere persistent (this skill's report output is the canonical place)

## See Also

- `hermes-agent` (bundled) — how to USE Hermes; this skill is the maintenance counterpart
- `hermes-troubleshooting/hermes-vision-pipeline` — diagnostic for one specific subsystem; consult when a post-update regression hits vision
- `hermes-troubleshooting/hermes-voice-mode` — same for voice

## References

- `templates/hermes-update.service` — known-good `Type=oneshot` systemd user unit that drives the update decoupled from the gateway (survives the gateway bounce). Uses `%h` so it's portable across users. Pair with the script below. Install to `~/.config/systemd/user/`, `daemon-reload`, pin target via `systemctl --user set-environment HERMES_UPDATE_TARGET=vX.Y.Z`, then `systemctl --user start hermes-update.service`. Proven on a 953-commit v0.15.2→v0.16.0 jump after three failed in-session attempts.
- `templates/hermes_self_update.sh` — the wrapper the oneshot unit runs: backup → stop gateway → checkout target → editable reinstall → migrate → doctor → restart. Logs to `~/.hermes/logs/self-update-<stamp>.log`, records rollback ref, restarts only the profile gateways that were active. Copy to `~/.hermes/scripts/`, `chmod +x`.
- `scripts/hermes_update_check.sh` — the weekly check script: silent when current, prints delta + safe-checkout + rollback when behind. Designed for `no_agent` cron use.
- `references/verifying-hermes-capability-presence.md` — five-place check (custom plugins → custom scripts → config wiring → session_search → upstream source) before claiming a Hermes capability is missing. Bit 2026-06-03 when agent grepped only upstream and confidently denied an existing user-built time-injection hook.
- `references/gateway-hooks-allowlist-and-env-propagation.md` — diagnosing wired-but-non-functional shell hooks: the two-gate model (`hooks_auto_accept` allowlist + systemd `EnvironmentFile=` env propagation). Includes the `hermes config set` path for the protected `config.yaml` and the unit-file edit. Bit 2026-06-03 chasing why `HERMES_ENABLE_LOCAL_TIME_CONTEXT` wasn't reaching the timestamp hook.
- `references/skill-stomp-protection-bundled-vs-user.md` — answering "will an update overwrite my skill edits?" The bundled (in-repo, git-tracked) vs. user (`~/.hermes/skills/`, what actually loads) two-copy model, the hash-gated bundled→user sync (`tools/skills_sync.py` — user edits diverge the dir hash → SKIPped forever → safe), a live verification recipe (`_dir_hash` vs `.bundled_manifest`), and the inverse risk people miss: a forked skill is pinned OFF upstream improvements. Verified 2026-06-07.
