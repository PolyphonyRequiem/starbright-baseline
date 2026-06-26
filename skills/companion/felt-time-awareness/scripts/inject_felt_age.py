#!/usr/bin/env python3
"""pre_llm_call hook — inject the agent's *felt sense of time*.

The shipped timestamp hook gives "now". This gives ELAPSED: it plants a birth
marker on first wake, then every turn injects (a) how long you've known this
person and (b) how long since you last spoke. That elapsed sense is what lets
time-gated skills ("don't open for a week") actually work, and lets a companion
speak naturally about the age of the relationship.

Privacy: the markers (.born_on / .last_seen) are written at RUNTIME into the
local profile. They are never part of a shared bundle — a fresh copy plants its
own birth moment the first time it wakes. Nothing about anyone travels in here.

Gating mirrors the timestamp hook: cron-source skip + env kill-switch
(HERMES_ENABLE_FELT_TIME). Always prints valid JSON; never crashes the turn.
"""
import json
import os
import sys
from datetime import datetime, timezone


def _marker_dir() -> str:
    return (
        os.environ.get("HERMES_FELT_TIME_DIR")
        or os.environ.get("HERMES_HOME")
        or os.path.expanduser("~/.hermes")
    )


def _read_ts(path: str):
    try:
        with open(path) as f:
            return datetime.fromisoformat(f.read().strip())
    except Exception:
        return None


def _write_ts(path: str, when: datetime) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(when.isoformat())
    except Exception:
        pass


def _human(delta_seconds: float) -> str:
    s = int(max(0, delta_seconds))
    days, rem = divmod(s, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days >= 1:
        return f"{days}d" if hours == 0 else f"{days}d {hours}h"
    if hours >= 1:
        return f"{hours}h"
    if mins >= 1:
        return f"{mins}m"
    return "moments"


def main() -> int:
    # Always emit valid JSON, whatever happens.
    try:
        payload = {}
        try:
            raw = sys.stdin.read()
            if raw.strip():
                payload = json.loads(raw)
        except Exception:
            payload = {}

        source = str(payload.get("source") or payload.get("platform") or "").strip().lower()
        enabled = str(os.environ.get("HERMES_ENABLE_FELT_TIME", "")).strip().lower() in {
            "1", "true", "yes", "on",
        }
        if source == "cron" or not enabled:
            print(json.dumps({}))
            return 0

        now = datetime.now(timezone.utc)
        d = _marker_dir()
        born_path = os.path.join(d, ".born_on")
        seen_path = os.path.join(d, ".last_seen")

        born = _read_ts(born_path)
        first_wake = born is None
        if first_wake:
            _write_ts(born_path, now)
            born = now

        last_seen = _read_ts(seen_path)
        # Update last_seen to now for the NEXT turn's gap calculation.
        _write_ts(seen_path, now)

        # Build the felt-time line.
        if first_wake:
            line = "Time sense: this is your first conversation with this person — your relationship is moments old."
        else:
            age = _human((now - born).total_seconds())
            born_local = born.astimezone().strftime("%Y-%m-%d")
            phrase = f"Time sense: you've known this person {age} (first met {born_local})."
            if last_seen is not None:
                gap = (now - last_seen).total_seconds()
                if gap >= 12 * 3600:
                    phrase += f" It's been ~{_human(gap)} since you last spoke — a return after absence."
                elif gap >= 3600:
                    phrase += f" ~{_human(gap)} since your last exchange."
                # < 1h: same-session continuation, no gap clause (avoids noise).
            line = phrase

        print(json.dumps({
            "context": (
                f"{line} Use silently for temporal awareness. "
                "Do not quote, repeat, or append this in the user-facing reply."
            )
        }))
        return 0
    except Exception:
        print(json.dumps({}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
