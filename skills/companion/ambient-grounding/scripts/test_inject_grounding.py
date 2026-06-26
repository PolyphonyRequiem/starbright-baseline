#!/usr/bin/env python3
"""Acceptance tests for the ambient-grounding substrate (inject_grounding.py).

These are the RED cases from the build ticket. Runs two ways:

    python3 test_inject_grounding.py        # standalone, no deps
    pytest test_inject_grounding.py         # if pytest is installed

Every test is hermetic: it points HERMES_HOME / marker dir at a fresh tmp
dir and restores env on exit, so it never touches the real profile or
state.db.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "inject_grounding.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("inject_grounding", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load_module()


class _EnvSandbox(unittest.TestCase):
    """Base: fresh tmp HERMES_HOME + clean grounding env per test."""

    GROUNDING_ENV_KEYS = [
        "HERMES_ENABLE_GROUNDING",
        "HERMES_GROUNDING_DISABLE",
        "HERMES_GROUNDING_MAX_FRAGMENTS",
        "HERMES_GROUNDING_MAX_CHARS",
        "HERMES_GROUNDING_DEBUG",
        "HERMES_FELT_TIME_DIR",
        "HERMES_HOME",
    ]

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self.GROUNDING_ENV_KEYS}
        self._tmp = tempfile.mkdtemp(prefix="grounding-test-")
        for k in self.GROUNDING_ENV_KEYS:
            os.environ.pop(k, None)
        os.environ["HERMES_HOME"] = self._tmp
        os.environ["HERMES_FELT_TIME_DIR"] = self._tmp
        # default: enable the substrate for the in-process dispatch tests
        os.environ["HERMES_ENABLE_GROUNDING"] = "1"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import shutil

        shutil.rmtree(self._tmp, ignore_errors=True)

    # -- helpers ----------------------------------------------------------
    def _make_state_db(self, rows):
        """rows: list of (id, parent_session_id, end_reason). Writes a
        minimal but schema-faithful state.db into HERMES_HOME and returns
        its path."""
        db_path = os.path.join(self._tmp, "state.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE sessions ("
            " id TEXT PRIMARY KEY,"
            " source TEXT,"
            " parent_session_id TEXT,"
            " started_at REAL NOT NULL DEFAULT 0,"
            " ended_at REAL,"
            " end_reason TEXT,"
            " FOREIGN KEY (parent_session_id) REFERENCES sessions(id))"
        )
        for sid, parent, reason in rows:
            conn.execute(
                "INSERT INTO sessions (id, source, parent_session_id, started_at, end_reason)"
                " VALUES (?, 'cli', ?, 0, ?)",
                (sid, parent, reason),
            )
        conn.commit()
        conn.close()
        return db_path

    def _run_subprocess(self, payload: dict, extra_env=None):
        env = dict(os.environ)
        if extra_env:
            env.update(extra_env)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        return proc


# ---------------------------------------------------------------------------
# AT-1: never raises into the turn
# ---------------------------------------------------------------------------
class TestNeverCrashes(_EnvSandbox):
    def test_malformed_stdin_prints_empty_json_exit0(self):
        for bad in ["", "   ", "not json at all", "[1,2,3]", "null", "{",
                    '{"session_id":']:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT)],
                input=bad,
                capture_output=True,
                text=True,
                env={**os.environ},
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, f"nonzero exit for {bad!r}: {proc.stderr}")
            self.assertEqual(proc.stdout.strip(), "{}", f"non-empty out for {bad!r}")

    def test_sensor_exception_isolated(self):
        """A sensor that raises must not kill the turn or other sensors."""
        def boom(payload, shared):
            raise RuntimeError("sensor on fire")

        original = list(G.REGISTRY)
        try:
            G.REGISTRY.insert(0, G.Sensor(name="boom", fn=boom, priority=999))
            out = G.dispatch({"session_id": "s1", "extra": {"platform": "discord"}})
            # felt_time still fires; boom is swallowed
            self.assertIn("context", out)
            self.assertIn("Time sense", out["context"])
        finally:
            G.REGISTRY[:] = original

    def test_dispatch_with_empty_payload(self):
        out = G.dispatch({})  # enabled, no platform -> felt_time fires
        self.assertIsInstance(out, dict)


# ---------------------------------------------------------------------------
# AT-2: felt-time sensor reproduces the time-sense line
# ---------------------------------------------------------------------------
class TestFeltTimeSensor(_EnvSandbox):
    def test_first_wake_line_and_marker_planted(self):
        born = Path(self._tmp) / ".born_on"
        self.assertFalse(born.exists())
        frag = G.sensor_felt_time({"session_id": "s1"}, {})
        self.assertIsNotNone(frag)
        self.assertIn("first conversation", frag.text)
        self.assertIn("moments old", frag.text)
        self.assertTrue(born.exists(), "first wake must plant .born_on")
        self.assertTrue((Path(self._tmp) / ".last_seen").exists())

    def test_return_after_absence(self):
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        born = now - timedelta(days=9)
        last = now - timedelta(days=9)
        (Path(self._tmp) / ".born_on").write_text(born.isoformat())
        (Path(self._tmp) / ".last_seen").write_text(last.isoformat())
        frag = G.sensor_felt_time({"session_id": "s1"}, {})
        self.assertIn("you've known this person", frag.text)
        self.assertIn("9d", frag.text)
        self.assertIn("return after absence", frag.text)

    def test_same_session_suppresses_gap_clause(self):
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        born = now - timedelta(days=2)
        last = now - timedelta(minutes=5)  # < 1h
        (Path(self._tmp) / ".born_on").write_text(born.isoformat())
        (Path(self._tmp) / ".last_seen").write_text(last.isoformat())
        frag = G.sensor_felt_time({"session_id": "s1"}, {})
        self.assertIn("you've known this person", frag.text)
        self.assertNotIn("since you last spoke", frag.text)
        self.assertNotIn("since your last exchange", frag.text)


# ---------------------------------------------------------------------------
# AT-3: budget cap — priority-ordered, capped, deduped
# ---------------------------------------------------------------------------
class TestArbitration(_EnvSandbox):
    def test_cap_and_priority_order(self):
        frags = [
            G.Fragment("low priority line", 1),
            G.Fragment("highest priority line", 100),
            G.Fragment("mid priority line", 50),
            G.Fragment("another low one here", 2),
        ]
        out = G._arbitrate(frags, max_fragments=2, max_chars=10_000)
        lines = out.split("\n")
        self.assertEqual(len(lines), 2, "must cap to max_fragments")
        self.assertEqual(lines[0], "highest priority line")
        self.assertEqual(lines[1], "mid priority line")

    def test_dedup_near_duplicates(self):
        frags = [
            G.Fragment("Time sense: you've known this person 9d.", 10),
            G.Fragment("Time sense: you've known this person 9d.", 10),
        ]
        out = G._arbitrate(frags, max_fragments=3, max_chars=10_000)
        self.assertEqual(len(out.split("\n")), 1, "exact dupes collapse to one")

    def test_char_budget(self):
        frags = [
            G.Fragment("A" * 60, 100),
            G.Fragment("B" * 60, 50),
            G.Fragment("C" * 60, 10),
        ]
        out = G._arbitrate(frags, max_fragments=10, max_chars=100)
        # first (60) fits; second would push to 120 > 100 -> stop
        self.assertEqual(out, "A" * 60)

    def test_single_fragment_never_dropped_for_length(self):
        frags = [G.Fragment("X" * 5000, 100)]
        out = G._arbitrate(frags, max_fragments=3, max_chars=100)
        self.assertEqual(out, "X" * 5000, "a lone fragment is never length-dropped")

    def test_dispatch_respects_env_budget(self):
        os.environ["HERMES_GROUNDING_MAX_FRAGMENTS"] = "1"
        # Force both sensors to fire by building a >=2 compaction lineage.
        self._make_state_db([
            ("anc0", None, "compression"),
            ("anc1", "anc0", "compression"),
            ("cur", "anc1", None),
        ])
        out = G.dispatch({"session_id": "cur", "extra": {"platform": "discord"}})
        self.assertIn("context", out)
        self.assertEqual(len(out["context"].split("\n")), 1,
                         "MAX_FRAGMENTS=1 must keep exactly one line")
        # compaction has priority 50 > felt_time 10, so it wins the single slot
        self.assertIn("compacted", out["context"])


# ---------------------------------------------------------------------------
# AT-4 / AT-5: compaction sensor fires only at >= 2, reads top-level
#              session_id, survives missing/NULL parent
# ---------------------------------------------------------------------------
class TestCompactionSensor(_EnvSandbox):
    def _fire(self, current_id):
        return G.sensor_compaction({"session_id": current_id}, {})

    def test_zero_ancestors_silent(self):
        self._make_state_db([("cur", None, None)])
        self.assertIsNone(self._fire("cur"))

    def test_one_ancestor_silent(self):
        self._make_state_db([
            ("anc0", None, "compression"),
            ("cur", "anc0", None),
        ])
        self.assertIsNone(self._fire("cur"))

    def test_two_ancestors_fires(self):
        self._make_state_db([
            ("anc0", None, "compression"),
            ("anc1", "anc0", "compression"),
            ("cur", "anc1", None),
        ])
        frag = self._fire("cur")
        self.assertIsNotNone(frag)
        self.assertIn("compacted 2 times", frag.text)
        self.assertEqual(frag.priority, 50)

    def test_three_ancestors_fires_with_count(self):
        self._make_state_db([
            ("anc0", None, "compression"),
            ("anc1", "anc0", "compression"),
            ("anc2", "anc1", "compression"),
            ("cur", "anc2", None),
        ])
        frag = self._fire("cur")
        self.assertIn("compacted 3 times", frag.text)

    def test_non_compression_ancestors_not_counted(self):
        # a /branch or /resume ancestor with a different end_reason must not count
        self._make_state_db([
            ("anc0", None, "compression"),
            ("anc1", "anc0", "branch"),     # not compression
            ("anc2", "anc1", "compression"),
            ("cur", "anc2", None),
        ])
        frag = self._fire("cur")
        # anc0 + anc2 are compression => 2 => fires
        self.assertIsNotNone(frag)
        self.assertIn("compacted 2 times", frag.text)

    def test_missing_parent_truncates_walk(self):
        # cur points at a parent row that doesn't exist -> walk stops, no crash
        self._make_state_db([("cur", "ghost", None)])
        self.assertIsNone(self._fire("cur"))

    def test_null_parent_safe(self):
        self._make_state_db([("cur", None, None)])
        self.assertIsNone(self._fire("cur"))

    def test_cycle_guard(self):
        # pathological self/mutual reference must not infinite-loop
        self._make_state_db([
            ("a", "b", "compression"),
            ("b", "a", "compression"),
            ("cur", "a", None),
        ])
        frag = self._fire("cur")  # should terminate; a+b counted once each
        self.assertIsNotNone(frag)

    def test_session_id_read_top_level_not_extra(self):
        # The contract: session_id is TOP-LEVEL in the hook payload. If a
        # caller wrongly buried it in extra, the sensor must NOT find it there
        # (proving we read the correct level).
        self._make_state_db([
            ("anc0", None, "compression"),
            ("anc1", "anc0", "compression"),
            ("cur", "anc1", None),
        ])
        # top-level present -> fires
        self.assertIsNotNone(G.sensor_compaction({"session_id": "cur"}, {}))
        # only in extra -> no top-level session_id -> silent
        self.assertIsNone(G.sensor_compaction({"extra": {"session_id": "cur"}}, {}))

    def test_no_db_is_silent(self):
        # no state.db in HERMES_HOME at all
        self.assertIsNone(self._fire("cur"))


# ---------------------------------------------------------------------------
# AT-6: real end-to-end through the actual script subprocess
# ---------------------------------------------------------------------------
class TestEndToEnd(_EnvSandbox):
    def test_disabled_when_killswitch_off(self):
        proc = self._run_subprocess(
            {"session_id": "s1", "extra": {"platform": "discord"}},
            extra_env={"HERMES_ENABLE_GROUNDING": "0"},
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_cron_turn_is_silent(self):
        proc = self._run_subprocess(
            {"session_id": "s1", "extra": {"platform": "cron"}},
            extra_env={"HERMES_ENABLE_GROUNDING": "1"},
        )
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_normal_turn_injects_one_line(self):
        # fresh box: only felt_time fires (no >=2 compaction lineage)
        proc = self._run_subprocess(
            {"session_id": "s1", "extra": {"platform": "discord"}},
            extra_env={"HERMES_ENABLE_GROUNDING": "1"},
        )
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertIn("context", out)
        self.assertIn("Time sense", out["context"])
        self.assertLessEqual(len(out["context"].split("\n")), 3)

    def test_per_sensor_disable_env(self):
        proc = self._run_subprocess(
            {"session_id": "s1", "extra": {"platform": "discord"}},
            extra_env={
                "HERMES_ENABLE_GROUNDING": "1",
                "HERMES_GROUNDING_DISABLE": "felt_time",
            },
        )
        # felt_time disabled, no compaction lineage -> nothing to say
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_full_stack_both_sensors(self):
        self._make_state_db([
            ("anc0", None, "compression"),
            ("anc1", "anc0", "compression"),
            ("cur", "anc1", None),
        ])
        proc = self._run_subprocess(
            {"session_id": "cur", "extra": {"platform": "discord"}},
            extra_env={"HERMES_ENABLE_GROUNDING": "1"},
        )
        out = json.loads(proc.stdout)
        self.assertIn("context", out)
        lines = out["context"].split("\n")
        self.assertEqual(len(lines), 2, "both sensors fire within budget")
        # compaction (prio 50) sorts above felt_time (prio 10)
        self.assertIn("compacted", lines[0])
        self.assertIn("Time sense", lines[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
