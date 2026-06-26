---
name: kde-plasma-session-recovery
description: Recover a frozen / unresponsive KDE Plasma desktop (e.g. Ubuntu 24.04 KDE) without a full logout — diagnose whether it's the compositor, the panel/shell, or a stuck lock screen, then apply the narrowest fix. Covers the xrdp multi-session reality, the loginctl unlock-session lever for a wedged screenlocker, and the systemd --user vs hand-respawn footgun. Use when the user says "my desktop/UI is frozen", "screen won't respond", "panel is gone", or "kwin/plasma is broken".
version: 1.0.0
author: Starbright (Hermes Agent)
license: private
platforms: [linux]
metadata:
  hermes:
    tags: [kde, plasma, kwin, linux, desktop, xrdp, session, troubleshooting]
    related_skills: [git-push-kwallet-askpass-hang, remote-command-execution-windows-linux]
    category: devops
---

# KDE Plasma Session Recovery

When the user says **"my UI is frozen"** / "the desktop won't respond" / "the panel
disappeared" / "kwin is broken" on a KDE box (e.g. Ubuntu 24.04 / KDE
Plasma 5.27, X11), the goal is **the narrowest fix that restores the session without
a logout** — apps stay alive, work isn't lost. The wrong move is to start
hand-restarting graphical processes before you know *which* component is actually
wedged.

> If your person is new to Linux and uses this box over **xrdp** a lot, explain the
> Linux-specific bits when they come up; prefer the supervised (systemd) path over
> hand-respawning processes.

## 🔴 Diagnose FIRST — three different failures look identical ("frozen")

A "frozen desktop" is one of three distinct things, each with a different fix.
**Don't restart anything until you've identified which.**

| Symptom source | What's actually wrong | The right lever |
|---|---|---|
| **Stuck lock screen** | `kscreenlocker_greet` wedged, grabbing all input | `loginctl unlock-session <id>` |
| **Compositor** | kwin hung — no window borders, tearing, black/frozen windows | `systemctl --user restart plasma-kwin_x11.service` |
| **Panel / shell** | taskbar gone, widgets frozen, but windows still move | `systemctl --user restart plasma-plasmashell.service` |

The single most-missed one is the **stuck lock screen** — it presents as a totally
dead desktop and a kwin restart does *nothing* for it. Check it first.

### Step 0 — rule out memory thrash before touching anything

On a box with OOM history, a "frozen" desktop can be memory thrash, in which case
restarting graphical services may fail or worsen it. Check first:

```bash
free -m | awk '/Mem:/{print "available_mb="$7}'
ps -eo pid,comm,rss --sort=-rss | head -7
```
If available memory is very low (< ~400 MB), do **not** restart the compositor —
report the memory pressure up and find the hog. If memory's fine, proceed.

### Step 1 — is the session LOCKED? (the most-missed cause)

```bash
loginctl list-sessions --no-legend          # find your session id (e.g. c4)
loginctl show-session <id> -p LockedHint -p Active -p Type -p Display
```
- **`LockedHint=yes`** → the session is locked, not frozen. This is the answer.
- Corroborate: `ps -eo pid,etimes,args | grep "[k]screenlocker_greet"` — if the
  greeter has an **enormous `etimes`** (e.g. 700,000s ≈ 8 days), it's a *stale,
  wedged* locker, not a fresh lock. That long-running-then-wedged shape is the tell.
- `pgrep kscreenlocker_greet` **silently returns nothing** — the process name
  exceeds 15 chars, so pgrep refuses to match. Use `ps … | grep "[k]screenlocker"`
  (full-cmdline grep) instead; a bare pgrep "no results" is a tooling artifact, NOT
  proof the locker is gone.

### Step 2 — if locked, unlock it the RIGHT way

The reliable lever is **logind**, not killing processes:

```bash
loginctl unlock-session <id>
```

- Then re-verify the **arbiter, not the process**: `loginctl show-session <id> -p
  LockedHint` should flip to `no`, and `qdbus org.freedesktop.ScreenSaver
  /ScreenSaver GetActive` should return `false`. All three agreeing (LockedHint=no,
  no greeter process, GetActive=false) = truly unlocked.
- **It can take a few seconds.** ksmserver releases the lock and reaps the greeter
  asynchronously — an immediate re-check may still show `LockedHint=yes` mid-teardown.
  Wait 2–3s and re-read before concluding it failed. (Verified 2026-06-17: the
  `unlock-session` returned exit 0, the immediate check still showed locked + a
  fresh greeter pid, and a few seconds later it was fully unlocked.)

## Why NOT to hand-respawn kwin/plasmashell (the footgun)

The instinct (and a lot of web advice) is:
```bash
kwin_x11 --replace &       # DON'T do this through an agent terminal
plasmashell --replace &
```
On this box **both kwin and plasmashell are systemd `--user` services**
(`plasma-kwin_x11.service`, `plasma-plasmashell.service` — confirmed by their
cgroups: `…/session.slice/plasma-kwin_x11.service`). So:

- `--replace &` backgrounded through an agent's terminal is dangerous: `--replace`
  kills the old compositor instantly, and if the tool reaps the backgrounded child
  when the call returns, the **new** one dies too → **no compositor at all** on a
  remote session, miserable to recover.
- The systemd restart is **supervised, persistent, and reap-proof** — same effect,
  no risk. **Rule of thumb: if a graphical component is a `systemctl --user` unit,
  let systemd cycle it; never hand-respawn it.** Verify membership with
  `systemctl --user list-units | grep -iE "plasma|kwin"`.

```bash
systemctl --user restart plasma-kwin_x11.service      # compositor (Wayland: plasma-kwin_wayland.service)
systemctl --user restart plasma-plasmashell.service   # panel / desktop shell
systemctl --user is-active plasma-kwin_x11.service     # verify: should print "active"
```

## X11 vs Wayland — pick the right binary/unit

```bash
echo "$XDG_SESSION_TYPE"                # x11 | wayland
ps -eo comm | grep -E "kwin_x11|kwin_wayland" | sort -u
```
This box runs **X11** (`kwin_x11`). Don't blindly use the Wayland variant —
restarting the wrong compositor unit does nothing useful.

## xrdp reality — there are usually TWO X servers; target the right one

Over xrdp this box has **multiple Xorg sessions**, and they are different desktops:

- A **physical-console** Xorg on `seat0`/`vt2` sitting at the **SDDM greeter** (the
  login screen on the actual monitor).
- Your **xrdp session** — its own Xorg on a high display like **`:10`**, running the
  live Plasma you're interacting with. `loginctl show-session <id>` shows
  `Type=x11`, `Display=:10`, `Remote=no`.

The agent's terminal lands on whichever `DISPLAY`/session it inherited (check `echo
$DISPLAY` and match it against `loginctl`). **Confirm which desktop the user is
actually looking at before restarting** — if they're on the physical monitor but you
fix `:10`, you fixed the wrong session. When unsure, ask: "physical screen or the
remote/RDP one?"

## Pitfalls

1. **Restarting kwin for a problem that's actually a stuck lock screen.** The most
   common waste. A kwin restart is harmless but does NOTHING for a wedged
   `kscreenlocker_greet`. Check `LockedHint` *first*. (Verified 2026-06-17: "UI
   completely frozen" was a screenlocker wedged for ~9 days; kwin was healthy.)
2. **`pgrep kscreenlocker_greet` returns nothing → assuming it's gone.** The name is
   >15 chars; pgrep silently no-matches. Use `ps … | grep "[k]screenlocker"`.
3. **Killing the greeter instead of unlocking the session.** `kill`ing
   `kscreenlocker_greet` makes ksmserver **respawn** it (the session is still flagged
   locked at the logind level), so you fight a respawn loop. Clear the *lock state*
   with `loginctl unlock-session`, don't chase the process.
4. **`qdbus … SetActive false` to unlock — doesn't work on a wedged locker.** The
   greeter ignores it. `loginctl unlock-session` is the lever that lands.
5. **Reading the immediate post-unlock state as failure.** The release is async;
   wait 2–3s and re-check `LockedHint` + `GetActive` before concluding.
6. **Hand-respawning systemd-managed kwin/plasmashell with `--replace &`.** Reap
   risk leaves you with no compositor. Use `systemctl --user restart`.
7. **Fixing the wrong xrdp session.** Match `$DISPLAY` to the user's actual screen.
8. **Restarting graphical services during memory thrash.** Rule out low-memory first.

## Quick reference (the 90% path)

```bash
ID=$(loginctl list-sessions --no-legend | awk '{print $1; exit}')
loginctl show-session "$ID" -p LockedHint -p Type -p Display   # locked? which display?
# If LockedHint=yes:
loginctl unlock-session "$ID"; sleep 3
loginctl show-session "$ID" -p LockedHint                       # expect: no
# If genuinely a dead compositor (not locked):
systemctl --user restart plasma-kwin_x11.service
# If panel/taskbar gone but windows fine:
systemctl --user restart plasma-plasmashell.service
```

## Unrelated-but-common noise

`plasma-kwallet-pam.service` often shows **failed** on xrdp (no PAM credential
passthrough to auto-unlock KWallet). It is **not** a compositor/lock-screen fault —
don't chase it when fixing a frozen UI. (KWallet-on-xrdp askpass hangs are a
separate issue — see `git-push-kwallet-askpass-hang`.)
