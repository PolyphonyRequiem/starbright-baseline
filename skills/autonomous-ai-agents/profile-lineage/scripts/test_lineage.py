#!/usr/bin/env python3
"""Acceptance tests for the profile-lineage substrate (lineage.py + reconcile.py).

Runs two ways:

    python3 test_lineage.py       # standalone, no deps beyond PyYAML
    pytest test_lineage.py        # if pytest is installed

Every test is hermetic: it builds fake profile dirs under a fresh tmp dir and
never touches a real Hermes profile.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


L = _load("lineage")
R = _load("reconcile")


def _mkprofile(root: Path, name: str, files: dict) -> Path:
    """Create a profile dir with the given {relpath: content} files."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return d


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_manifest_covers_only_distribution_owned(self):
        d = _mkprofile(
            self.tmp,
            "p",
            {
                "SOUL.md": "posture",
                "skills/x/SKILL.md": "skill x",
                # user-owned — must be excluded:
                "config.yaml": "model: {}",
                ".env": "SECRET=1",
                "memories/MEMORY.md": "private",
                "sessions/state.db": "binary-ish",
                "logs/agent.log": "noise",
            },
        )
        m = L.compute_manifest(d)
        self.assertIn("SOUL.md", m)
        self.assertIn("skills/x/SKILL.md", m)
        for excluded in ("config.yaml", ".env", "memories/MEMORY.md",
                         "sessions/state.db", "logs/agent.log"):
            self.assertNotIn(excluded, m, f"{excluded} leaked into manifest")

    def test_manifest_roundtrip(self):
        d = _mkprofile(self.tmp, "p", {"SOUL.md": "x", "skills/a/SKILL.md": "y"})
        L.write_manifest(d)
        back = L.read_manifest(d)
        self.assertEqual(set(back), {"SOUL.md", "skills/a/SKILL.md"})
        # manifest never hashes itself
        self.assertNotIn(L.MANIFEST_FILENAME, back)

    def test_drift_detects_modify_add_remove(self):
        d = _mkprofile(self.tmp, "p", {"SOUL.md": "v1", "skills/a/SKILL.md": "a"})
        L.write_manifest(d)
        # modify SOUL, add a new skill, remove skills/a
        (d / "SOUL.md").write_text("v2", encoding="utf-8")
        (d / "skills" / "b").mkdir(parents=True)
        (d / "skills" / "b" / "SKILL.md").write_text("b", encoding="utf-8")
        (d / "skills" / "a" / "SKILL.md").unlink()
        rep = L.compute_drift(d)
        self.assertFalse(rep.clean)
        self.assertEqual(rep.modified, ["SOUL.md"])
        self.assertEqual(rep.added, ["skills/b/SKILL.md"])
        self.assertEqual(rep.removed, ["skills/a/SKILL.md"])

    def test_clean_when_untouched(self):
        d = _mkprofile(self.tmp, "p", {"SOUL.md": "v1"})
        L.write_manifest(d)
        self.assertTrue(L.compute_drift(d).clean)

    def test_editing_userland_never_shows_drift(self):
        d = _mkprofile(self.tmp, "p", {"SOUL.md": "v1"})
        L.write_manifest(d)
        # user edits their config + memory — must NOT count as distribution drift
        (d / "config.yaml").write_text("model: {provider: x}", encoding="utf-8")
        (d / "memories").mkdir(exist_ok=True)
        (d / "memories" / "MEMORY.md").write_text("secret", encoding="utf-8")
        self.assertTrue(L.compute_drift(d).clean)

    def test_lineage_yaml_never_in_manifest_or_drift(self):
        # lineage.yaml is per-profile identity, not distribution content.
        d = _mkprofile(self.tmp, "p", {"SOUL.md": "v1"})
        L.write_lineage(d, L.Lineage(this="p", event="root", roots=["p"]))
        m = L.compute_manifest(d)
        self.assertNotIn("lineage.yaml", m)
        L.write_manifest(d)
        # changing lineage.yaml must not register as drift
        L.write_lineage(d, L.Lineage(this="p", event="fork",
                        parents=[L.ParentEdge(name="q")]))
        self.assertTrue(L.compute_drift(d).clean)


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_record_single_fork(self):
        parent = _mkprofile(self.tmp, "base", {"SOUL.md": "x"})
        L.write_lineage(parent, L.Lineage(this="base", event="root", roots=["base"], ancestry=[]))
        child = _mkprofile(self.tmp, "child", {"SOUL.md": "x"})
        lin = L.record_edge(
            child, this_name="child", event="fork",
            parent=L.ParentEdge(name="base", source=str(parent), version="1.0.0", sha="abc123"),
            event_reason="specialize",
        )
        L.write_lineage(child, lin)
        back = L.read_lineage(child)
        self.assertEqual(back.this, "child")
        self.assertEqual(back.event, "fork")
        self.assertEqual(back.parent_names(), ["base"])
        self.assertIn("base", back.ancestry)
        self.assertEqual(back.parents[0].sha, "abc123")

    def test_multiple_parents_join(self):
        base = _mkprofile(self.tmp, "base", {"SOUL.md": "x"})
        L.write_lineage(base, L.Lineage(this="base", event="root", roots=["base"]))
        fe = _mkprofile(self.tmp, "fe", {"SOUL.md": "x"})
        L.write_lineage(fe, L.record_edge(fe, "fe", "fork",
                        L.ParentEdge(name="base", source=str(base))))
        be = _mkprofile(self.tmp, "be", {"SOUL.md": "x"})
        L.write_lineage(be, L.record_edge(be, "be", "fork",
                        L.ParentEdge(name="base", source=str(base))))
        # join fe + be -> full
        full = _mkprofile(self.tmp, "full", {"SOUL.md": "x"})
        lin = L.record_edge(full, "full", "join",
                            L.ParentEdge(name="fe", source=str(fe)), event_reason="unify")
        lin = L.record_edge(full, "full", "join",
                            L.ParentEdge(name="be", source=str(be)), into=lin)
        L.write_lineage(full, lin)
        back = L.read_lineage(full)
        self.assertEqual(back.event, "join")
        self.assertEqual(set(back.parent_names()), {"fe", "be"})
        self.assertIn("base", back.ancestry)  # closure pulled through both parents

    def test_lca_of_siblings_is_baseline(self):
        base = _mkprofile(self.tmp, "base", {"SOUL.md": "x"})
        L.write_lineage(base, L.Lineage(this="base", event="root", roots=["base"]))
        fe = _mkprofile(self.tmp, "fe", {"SOUL.md": "x"})
        L.write_lineage(fe, L.record_edge(fe, "fe", "fork", L.ParentEdge(name="base", source=str(base))))
        be = _mkprofile(self.tmp, "be", {"SOUL.md": "x"})
        L.write_lineage(be, L.record_edge(be, "be", "fork", L.ParentEdge(name="base", source=str(base))))
        mb = L.merge_base([L.read_lineage(fe), L.read_lineage(be)])
        self.assertEqual(mb, "base")

    def test_lca_none_when_unrelated(self):
        a = L.Lineage(this="a", roots=["a"], ancestry=[])
        b = L.Lineage(this="b", roots=["b"], ancestry=[])
        self.assertIsNone(L.merge_base([a, b]))


class ReconcileTests(unittest.TestCase):
    def test_auto_resolvable_cases(self):
        base = {"a": "H", "b": "H", "c": "H"}
        ours = {"a": "H", "b": "X", "c": "H", "d": "N"}   # edit b, add d
        theirs = {"a": "Y", "b": "H", "c": "H"}           # edit a
        res = R.classify(base, ours, theirs)
        self.assertEqual(res.conflicts, [])
        self.assertEqual(res.auto["a"], "theirs-only")
        self.assertEqual(res.auto["b"], "ours-only")
        self.assertEqual(res.auto["c"], "unchanged")
        self.assertEqual(res.auto["d"], "add-ours")

    def test_true_conflict_edit_vs_edit(self):
        base = {"a": "H"}
        ours = {"a": "X"}
        theirs = {"a": "Y"}
        res = R.classify(base, ours, theirs)
        self.assertEqual(len(res.conflicts), 1)
        self.assertEqual(res.conflicts[0]["kind"], "edit-vs-edit")

    def test_convergent_edit_is_not_conflict(self):
        base = {"a": "H"}
        ours = {"a": "SAME"}
        theirs = {"a": "SAME"}
        res = R.classify(base, ours, theirs)
        self.assertEqual(res.conflicts, [])
        self.assertEqual(res.auto["a"], "same-edit")

    def test_edit_vs_delete_conflict(self):
        base = {"a": "H"}
        ours = {"a": "X"}       # edited
        theirs = {}             # deleted
        res = R.classify(base, ours, theirs)
        self.assertEqual(len(res.conflicts), 1)
        self.assertEqual(res.conflicts[0]["kind"], "edit-vs-delete")

    def test_add_both_differ_conflict(self):
        base = {}
        ours = {"new": "X"}
        theirs = {"new": "Y"}
        res = R.classify(base, ours, theirs)
        self.assertEqual(len(res.conflicts), 1)
        self.assertEqual(res.conflicts[0]["kind"], "add-both-differ")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _run(self, script, *args):
        return subprocess.run(
            [sys.executable, str(HERE / script), *args],
            capture_output=True, text=True,
        )

    def test_cli_manifest_and_drift(self):
        d = _mkprofile(self.tmp, "p", {"SOUL.md": "v1"})
        r = self._run("lineage.py", "manifest-gen", str(d))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["files"], 1)
        # clean drift -> exit 0
        r = self._run("lineage.py", "drift", str(d))
        self.assertEqual(r.returncode, 0)
        # dirty -> exit 1
        (d / "SOUL.md").write_text("v2", encoding="utf-8")
        r = self._run("lineage.py", "drift", str(d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("SOUL.md", json.loads(r.stdout)["modified"])

    def test_cli_classify_exit_codes(self):
        base = _mkprofile(self.tmp, "base", {"SOUL.md": "H", "s/SKILL.md": "H"})
        ours = _mkprofile(self.tmp, "ours", {"SOUL.md": "H", "s/SKILL.md": "X"})
        theirs = _mkprofile(self.tmp, "theirs", {"SOUL.md": "H", "s/SKILL.md": "H"})
        # only ours edited -> auto, exit 0
        r = self._run("reconcile.py", "classify", "--base", str(base),
                      "--ours", str(ours), "--theirs", str(theirs))
        self.assertEqual(r.returncode, 0, r.stderr)
        # make theirs edit the same file differently -> conflict, exit 1
        (theirs / "s" / "SKILL.md").write_text("Y", encoding="utf-8")
        r = self._run("reconcile.py", "classify", "--base", str(base),
                      "--ours", str(ours), "--theirs", str(theirs))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["summary"]["conflict_count"], 1)


def _find_posix_bash() -> str | None:
    """Locate a POSIX bash that can run check-drift.sh.

    On Windows a bare ``bash`` resolves to WSL's launcher, which fails with
    ``execvpe(/bin/bash)`` when no distro is installed — so prefer git-bash's
    real binary. Elsewhere plain ``bash`` on PATH is fine. Returns None when no
    usable bash exists (the shell-wrapper tests then skip).
    """
    import shutil

    candidates = [
        shutil.which("bash"),
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\bin\bash.exe",
        "/usr/bin/bash",
        "/bin/bash",
    ]
    for c in candidates:
        if not c or not Path(c).exists():
            continue
        # WSL's bare 'bash' is on PATH but can't exec /bin/bash — probe it.
        try:
            probe = subprocess.run([c, "-c", "echo ok"], capture_output=True, text=True, timeout=15)
        except Exception:
            continue
        if probe.returncode == 0 and probe.stdout.strip() == "ok":
            return c
    return None


class ShellWrapperTests(unittest.TestCase):
    """check-drift.sh is the git-free drift entry point; verify its exit codes
    under a real POSIX bash (its actual runtime), not WSL's stub."""

    def setUp(self):
        self.bash = _find_posix_bash()
        if not self.bash:
            self.skipTest("no POSIX bash available (git-bash / bash) to run check-drift.sh")
        self.tmp = Path(tempfile.mkdtemp())
        self.script = str(HERE / "check-drift.sh")

    def _sh(self, *args):
        return subprocess.run([self.bash, self.script, *args], capture_output=True, text=True)

    def test_check_drift_clean_dirty_regen(self):
        d = _mkprofile(self.tmp, "p", {"SOUL.md": "v1"})
        # baseline first so the wrapper has a manifest to compare against
        subprocess.run([sys.executable, str(HERE / "lineage.py"), "manifest-gen", str(d)],
                       capture_output=True, check=True)
        # clean -> exit 0
        self.assertEqual(self._sh(str(d)).returncode, 0)
        # drifted -> exit 1, names the file
        (d / "SOUL.md").write_text("v2", encoding="utf-8")
        drift = self._sh(str(d))
        self.assertEqual(drift.returncode, 1)
        self.assertIn("SOUL.md", drift.stdout)
        # --regen rewrites the baseline -> exit 0, clean again
        self.assertEqual(self._sh("--regen", str(d)).returncode, 0)
        self.assertEqual(self._sh(str(d)).returncode, 0)

    def test_check_drift_missing_manifest_usage_error(self):
        d = _mkprofile(self.tmp, "nomanifest", {"SOUL.md": "v1"})
        # no manifest generated -> usage error (exit 2), not a false "clean"
        self.assertEqual(self._sh(str(d)).returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
