#!/usr/bin/env python3
"""pre_llm_call hook — the ambient-grounding *substrate*.

ONE dispatcher, many sensors, one budget. This replaces the "N blind
injectors" pattern (several independent `pre_llm_call:` command lines that
can't see each other, can't suppress each other, and can't share a budget)
with a single process that:

  1. parses the hook stdin payload exactly once,
  2. applies a central kill-switch + cron-skip,
  3. runs an ordered registry of *sensors*, each of which may emit a short
     grounding fragment,
  4. arbitrates the fragments — priority-rank, per-turn budget cap, dedup —
     into one block appended to the turn, and
  5. NEVER raises into the turn: any failure prints `{}` and exits 0.

Why a substrate and not four hooks: four blind `pre_llm_call` injectors can't
suppress each other or share a budget; one dispatcher with a sensor registry
and a per-turn cap can. Adding a new kind of ambient awareness = adding one
function to REGISTRY, not another subprocess.

Wire protocol (Hermes pre_llm_call shell hook):
  stdin  : JSON  {"hook_event_name","tool_name","tool_input","session_id",
                  "cwd","extra":{...}}   <- only session_id is top-level;
                  platform/is_first_turn/model/etc. live under "extra".
  stdout : JSON  {"context": "<text>"}   to inject, or  {}  for silent no-op.

Gating (two-stage, mirrors the shipped timestamp/felt-time hooks):
  * master kill-switch  : env HERMES_ENABLE_GROUNDING must be truthy, else
                          the whole substrate is a silent no-op. Wiring the
                          hook is harmless until this flag flips on.
  * cron-skip           : scheduled (platform == "cron") turns never inject.
  * per-sensor opt-out  : env HERMES_GROUNDING_DISABLE="felt_time,compaction"
                          drops named sensors without unwiring anything.

Tunables (env, all optional):
  HERMES_GROUNDING_MAX_FRAGMENTS  default 3   hard cap on lines per turn
  HERMES_GROUNDING_MAX_CHARS      default 800 secondary char budget
  HERMES_GROUNDING_DEBUG          truthy -> diagnostics to stderr (logged at
                                  debug by the hook runner; never on stdout)

Privacy: sensors read turn metadata + the local state.db; they store no
message text. The felt-time sensor writes two timestamp markers into the
local profile home and nothing else (see sensor_felt_time).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Callable, Dict, List, NamedTuple, Optional

# ---------------------------------------------------------------------------
# Fragment + sensor contract
# ---------------------------------------------------------------------------


class Fragment(NamedTuple):
    """A single self-contained grounding line a sensor wants to inject.

    `text` carries its OWN use-instruction (e.g. "...use silently; don't
    quote it back."). The dispatcher is a pure arbitration layer — it does
    not editorialize a sensor's framing. `priority`: higher wins the budget
    and sorts first; registry order breaks ties (stable sort).
    """

    text: str
    priority: int


# Sensor signature: fn(payload: dict, shared: dict) -> Optional[Fragment]
#   payload  - the parsed hook stdin (session_id top-level; rest under extra)
#   shared   - dispatcher scratch dict, shared across sensors in ONE turn so
#              DB-touching sensors reuse a single state.db connection.
SensorFn = Callable[[dict, dict], Optional[Fragment]]


class Sensor(NamedTuple):
    name: str
    fn: SensorFn
    priority: int


# ---------------------------------------------------------------------------
# Payload helpers — THE load-bearing gotcha lives here
# ---------------------------------------------------------------------------


def _meta(payload: dict, key: str, default=None):
    """Read a per-turn metadata value.

    Real hook payloads (agent/shell_hooks.py::_serialize_payload) nest
    everything except `session_id` under `payload["extra"]`. Hand-crafted
    test stdin may put a key top-level. Prefer `extra`, fall back to
    top-level — so both production and `echo '{...}' | inject_grounding.py`
    behave the same. (Reading `extra` keys top-level is the latent bug in
    the original felt-time hook; the substrate fixes it centrally.)
    """
    extra = payload.get("extra")
    if isinstance(extra, dict) and key in extra:
        return extra[key]
    return payload.get(key, default)


def _truthy(val) -> bool:
    return str(val or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, "")).strip())
    except (TypeError, ValueError):
        return default


def _debug(msg: str) -> None:
    if _truthy(os.environ.get("HERMES_GROUNDING_DEBUG")):
        print(f"[inject_grounding] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Central skip — master kill-switch + cron guard
# ---------------------------------------------------------------------------


def _should_skip(payload: dict) -> bool:
    if not _truthy(os.environ.get("HERMES_ENABLE_GROUNDING")):
        _debug("skip: HERMES_ENABLE_GROUNDING not truthy")
        return True
    # cron-skip: scheduled turns get no ambient grounding prefix. Read platform
    # from extra (the gotcha) with a source/top-level fallback.
    plat = _meta(payload, "platform") or _meta(payload, "source") or ""
    if str(plat).strip().lower() == "cron":
        _debug("skip: cron-sourced turn")
        return True
    return False


def _disabled_sensors() -> set:
    raw = os.environ.get("HERMES_GROUNDING_DISABLE", "")
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


# ---------------------------------------------------------------------------
# Shared state.db connection (read-only) for DB-touching sensors
# ---------------------------------------------------------------------------


def _get_db(shared: dict):
    """Return a cached read-only sqlite3 connection to this profile's
    state.db, or None. Resolves via HERMES_HOME (the hook subprocess
    inherits the gateway's env, so this is the SAME db the agent writes
    sessions to — agent/hermes_state.py:34 DEFAULT_DB_PATH). Opened once
    per turn and reused by every sensor via `shared`.
    """
    if "db_conn" in shared:
        return shared["db_conn"]
    conn = None
    try:
        import sqlite3

        home = (
            os.environ.get("HERMES_HOME")
            or os.path.expanduser("~/.hermes")
        )
        db_path = os.path.join(home, "state.db")
        if os.path.exists(db_path):
            # mode=ro: never take a write lock; WAL readers don't block the
            # gateway writer. timeout small so we never stall a turn.
            uri = f"file:{db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=1.0)
    except Exception as exc:  # pragma: no cover - defensive
        _debug(f"db open failed: {exc!r}")
        conn = None
    shared["db_conn"] = conn
    return conn


# ---------------------------------------------------------------------------
# Sensor #1 — felt time (ported from felt-time-awareness/inject_felt_age.py)
# ---------------------------------------------------------------------------


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


def sensor_felt_time(payload: dict, shared: dict) -> Optional[Fragment]:
    """Inject the agent's felt sense of *elapsed* time: how long it's known
    this person and how long since they last spoke. Plants a birth marker on
    first wake; updates a last-seen marker every turn for the next gap calc.

    Side effect: writes .born_on / .last_seen under the marker dir. No
    message content is read or stored. Privacy design unchanged from the
    original felt-time hook.
    """
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
    _write_ts(seen_path, now)  # for the NEXT turn's gap calculation

    if first_wake:
        line = (
            "Time sense: this is your first conversation with this person — "
            "your relationship is moments old."
        )
    else:
        age = _human((now - born).total_seconds())
        born_local = born.astimezone().strftime("%Y-%m-%d")
        line = f"Time sense: you've known this person {age} (first met {born_local})."
        if last_seen is not None:
            gap = (now - last_seen).total_seconds()
            if gap >= 12 * 3600:
                line += f" It's been ~{_human(gap)} since you last spoke — a return after absence."
            elif gap >= 3600:
                line += f" ~{_human(gap)} since your last exchange."
            # < 1h: same-session continuation, no gap clause (avoids noise).

    text = (
        f"{line} Use silently for temporal awareness; "
        "don't quote it back."
    )
    return Fragment(text=text, priority=10)


# ---------------------------------------------------------------------------
# Sensor #2 — compaction lineage
# ---------------------------------------------------------------------------


def _count_compression_ancestors(conn, session_id: str) -> int:
    """Walk parent_session_id upward from `session_id`, counting ancestors
    whose end_reason == 'compression'.

    Mechanic (verified against source): every compaction splits the session —
    the old row is end_session()'d with reason 'compression' (first-end-reason
    wins, agent/hermes_state.py:978) and the NEW row gets
    parent_session_id = old_id (agent/conversation_compression.py:507,522).
    So "# of compactions in this lineage" == "# of ancestors with
    end_reason='compression'". The CURRENT session's end_reason is NULL, so we
    start from its PARENT and count up. Cycle-guarded; survives NULL/missing
    parents (a pruned ancestor just truncates the walk).
    """
    count = 0
    seen = set()
    row = conn.execute(
        "SELECT parent_session_id FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    cur = row[0] if row else None
    while cur and cur not in seen:
        seen.add(cur)
        r = conn.execute(
            "SELECT parent_session_id, end_reason FROM sessions WHERE id = ?",
            (cur,),
        ).fetchone()
        if r is None:
            break
        parent, end_reason = r[0], r[1]
        if (end_reason or "") == "compression":
            count += 1
        cur = parent
    return count


def sensor_compaction(payload: dict, shared: dict) -> Optional[Fragment]:
    """Fire when this lineage has compacted >= 2 times — a signal that
    context quality is degrading and a fresh, deliberately-handed-off session
    would beat continuing to ride a twice-summarized context.
    """
    session_id = payload.get("session_id")  # top-level by contract
    if not session_id:
        return None
    conn = _get_db(shared)
    if conn is None:
        return None
    try:
        n = _count_compression_ancestors(conn, str(session_id))
    except Exception as exc:
        _debug(f"compaction walk failed: {exc!r}")
        return None
    if n < 2:
        return None
    text = (
        f"Session-health note: this conversation's context has been compacted "
        f"{n} times, and accuracy degrades with each pass. Strongly consider "
        "writing a dense handoff now (open threads, decisions made, next "
        "concrete steps), tying off loose ends, and starting a fresh session. "
        "Use your judgment; don't mention this note verbatim."
    )
    return Fragment(text=text, priority=50)


# ---------------------------------------------------------------------------
# Registry — ordered. Add a sensor here; that's the whole extension surface.
# ---------------------------------------------------------------------------

REGISTRY: List[Sensor] = [
    Sensor(name="felt_time", fn=sensor_felt_time, priority=10),
    Sensor(name="compaction", fn=sensor_compaction, priority=50),
]


# ---------------------------------------------------------------------------
# Arbitration — priority-rank + budget cap + dedup
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _is_dup(norm: str, seen: List[str]) -> bool:
    if not norm:
        return True
    for k in seen:
        if norm == k:
            return True
        # near-dupe: one fully contains the other, and the contained string is
        # long enough that the overlap is meaningful (avoids trivial matches).
        if len(norm) >= 16 and (norm in k or k in norm):
            return True
    return False


def _arbitrate(
    fragments: List[Fragment], max_fragments: int, max_chars: int
) -> str:
    """Rank fragments by priority (desc, stable), drop near-dupes, and keep
    at most `max_fragments` within a `max_chars` budget. Always keeps at
    least one fragment if any survive dedup (a single high-priority line is
    never dropped for length). Returns the joined block, or "".
    """
    ranked = sorted(fragments, key=lambda f: -f.priority)
    kept: List[str] = []
    seen_norm: List[str] = []
    total = 0
    for f in ranked:
        norm = _normalize(f.text)
        if _is_dup(norm, seen_norm):
            continue
        if len(kept) >= max_fragments:
            break
        if kept and total + len(f.text) > max_chars:
            break
        kept.append(f.text)
        seen_norm.append(norm)
        total += len(f.text)
    return "\n".join(kept)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def dispatch(payload: dict) -> dict:
    """Pure-ish core: payload in, wire-shape dict out. Separated from main()
    so tests can drive it directly without a subprocess."""
    if _should_skip(payload):
        return {}

    disabled = _disabled_sensors()
    shared: Dict[str, object] = {}
    fragments: List[Fragment] = []
    for sensor in REGISTRY:
        if sensor.name.lower() in disabled:
            _debug(f"sensor {sensor.name} disabled by env")
            continue
        try:
            frag = sensor.fn(payload, shared)
        except Exception as exc:
            # one sensor failing NEVER kills the turn or the other sensors.
            _debug(f"sensor {sensor.name} raised: {exc!r}")
            continue
        if frag is None:
            continue
        if isinstance(frag, str):  # lenient coercion
            frag = Fragment(text=frag, priority=sensor.priority)
        if isinstance(frag, Fragment) and frag.text and frag.text.strip():
            fragments.append(frag)

    # close any DB connection the sensors opened
    conn = shared.get("db_conn")
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    if not fragments:
        return {}

    merged = _arbitrate(
        fragments,
        max_fragments=_env_int("HERMES_GROUNDING_MAX_FRAGMENTS", 3),
        max_chars=_env_int("HERMES_GROUNDING_MAX_CHARS", 800),
    )
    _debug(f"{len(fragments)} fragment(s) -> {len(merged)} chars injected")
    return {"context": merged} if merged else {}


def main() -> int:
    # Always emit valid JSON, whatever happens. A broken hook must never crash
    # the turn (the runner tolerates it, but we belt-and-suspenders here too).
    #
    # Abstain (print {}) unless stdin parses to a dict. In production the hook
    # runner ALWAYS sends a serialized dict payload (shell_hooks._serialize_
    # payload), so this never abstains in real use — it only fires on
    # empty/broken/non-dict input, where the safe move is silence: we don't
    # want to run felt-time's marker-writing side effect on a spurious or
    # malformed invocation (it would skew the elapsed-time gap calc).
    try:
        raw = sys.stdin.read()
    except Exception:
        print("{}")
        return 0
    if not raw.strip():
        print("{}")
        return 0
    try:
        payload = json.loads(raw)
    except Exception:
        print("{}")
        return 0
    if not isinstance(payload, dict):
        print("{}")
        return 0
    try:
        out = dispatch(payload)
    except Exception as exc:  # pragma: no cover - last-ditch guard
        _debug(f"dispatch raised: {exc!r}")
        out = {}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
