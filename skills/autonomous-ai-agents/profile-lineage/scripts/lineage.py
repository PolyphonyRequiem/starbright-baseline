#!/usr/bin/env python3
"""profile-lineage — the substrate library for the profile-ops skill family.

A Hermes *distribution* profile can be forked, split, joined, and repurposed.
This module is the source of truth for **where a profile came from** and
**whether its distribution-owned files have drifted** from what was shipped.

It is deliberately dependency-light (PyYAML + stdlib) and side-effect-free at
import time so the sibling skills (profile-overload-watch, profile-refactor,
profile-reconcile) can import it as a library, and a human can run it as a CLI.

Three concerns, three record types:

  1. lineage.yaml         — the ancestry DAG (multiple parents supported).
  2. distribution.manifest — path:sha256 of every distribution-owned file, the
                             drift baseline (mirrors Hermes' .bundled_manifest).
  3. LCA / merge-base      — lowest common ancestor in the DAG, used by
                             profile-reconcile for 3-way merges.

CLI:
    lineage.py manifest-gen  <profile_dir>            # write distribution.manifest
    lineage.py drift         <profile_dir>            # report drift vs manifest
    lineage.py show          <profile_dir>            # print lineage summary
    lineage.py lca           <A.yaml> <B.yaml> ...    # lowest common ancestor
    lineage.py record-fork   <child_dir> --parent ... # append a lineage edge

Every subcommand prints JSON to stdout and exits non-zero on error, so it is
scriptable from bash and from the agent skills.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover — PyYAML is a Hermes hard dep
    sys.stderr.write("PyYAML is required for lineage.py\n")
    sys.exit(3)

LINEAGE_FILENAME = "lineage.yaml"
MANIFEST_FILENAME = "distribution.manifest"
SCHEMA_VERSION = 2  # v2 = DAG (multiple parents); v1 was single-parent tree

# Files/dirs that are USER-owned and therefore never part of lineage or the
# drift baseline. Mirrors the installer's USER_OWNED_EXCLUDE so the drift set
# is exactly the distribution-owned surface.
USER_OWNED = {
    ".env",
    ".env.EXAMPLE",
    "auth.json",
    "auth.lock",
    "config.yaml",
    "memories",
    "sessions",
    "logs",
    "cache",
    "audio_cache",
    "image_cache",
    "media_cache",
    "workspace",
    "home",
    "plans",
    "pairing",
    "skins",
    ".git",
    "state.db",
    "state.db-shm",
    "state.db-wal",
    # lineage's own baseline must not hash itself
    MANIFEST_FILENAME,
    # lineage.yaml is per-profile identity metadata (each fork has its own),
    # NOT distribution content to diff/merge — exclude like config.yaml.
    LINEAGE_FILENAME,
}
# Extensions that are runtime junk even inside distribution-owned dirs.
_JUNK_SUFFIXES = {".pyc", ".log", ".lock", ".db", ".db-shm", ".db-wal", ".tmp"}


# ---------------------------------------------------------------------------
# lineage.yaml model  (the ancestry DAG)
# ---------------------------------------------------------------------------
@dataclass
class ParentEdge:
    """One immediate ancestor edge — the source of truth in the DAG."""

    name: str
    source: str = ""
    version: str = ""
    sha: str = ""
    at: str = ""
    reason: str = ""

    @classmethod
    def from_dict(cls, d: Any) -> "ParentEdge":
        if not isinstance(d, dict):
            raise ValueError(f"parent edge must be a mapping, got {type(d).__name__}")
        name = str(d.get("name") or "").strip()
        if not name:
            raise ValueError("parent edge missing 'name'")
        return cls(
            name=name,
            source=str(d.get("source") or ""),
            version=str(d.get("version") or ""),
            sha=str(d.get("sha") or ""),
            at=str(d.get("at") or ""),
            reason=str(d.get("reason") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"name": self.name}
        for k in ("source", "version", "sha", "at", "reason"):
            v = getattr(self, k)
            if v:
                out[k] = v
        return out


@dataclass
class Lineage:
    """The ancestry record for one profile.

    ``parents`` are the immediate edges (truth). ``ancestry`` is a cached
    closure snapshot (convenience that may lag — recompute from edges when a
    definitive answer is needed and the ancestor files are reachable).
    """

    this: str
    event: str = "fork"  # fork | split | join | repurpose | root
    event_reason: str = ""
    parents: List[ParentEdge] = field(default_factory=list)
    roots: List[str] = field(default_factory=list)
    ancestry: List[str] = field(default_factory=list)
    schema: int = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, d: Any) -> "Lineage":
        if not isinstance(d, dict):
            raise ValueError(f"{LINEAGE_FILENAME} must be a mapping")
        this = str(d.get("this") or "").strip()
        if not this:
            raise ValueError(f"{LINEAGE_FILENAME} missing 'this'")
        parents_raw = d.get("parents") or []
        if not isinstance(parents_raw, list):
            raise ValueError("'parents' must be a list")
        parents = [ParentEdge.from_dict(p) for p in parents_raw]
        return cls(
            this=this,
            event=str(d.get("event") or "fork"),
            event_reason=str(d.get("event_reason") or ""),
            parents=parents,
            roots=[str(r).strip() for r in (d.get("roots") or []) if str(r).strip()],
            ancestry=[str(a).strip() for a in (d.get("ancestry") or []) if str(a).strip()],
            schema=int(d.get("schema") or SCHEMA_VERSION),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"schema": self.schema, "this": self.this, "event": self.event}
        if self.event_reason:
            out["event_reason"] = self.event_reason
        if self.parents:
            out["parents"] = [p.to_dict() for p in self.parents]
        if self.roots:
            out["roots"] = list(self.roots)
        if self.ancestry:
            out["ancestry"] = list(self.ancestry)
        return out

    def parent_names(self) -> List[str]:
        return [p.name for p in self.parents]


def read_lineage(profile_dir: Path) -> Optional[Lineage]:
    p = Path(profile_dir) / LINEAGE_FILENAME
    if not p.is_file():
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Lineage.from_dict(data or {})


def write_lineage(profile_dir: Path, lin: Lineage) -> Path:
    p = Path(profile_dir) / LINEAGE_FILENAME
    p.write_text(
        yaml.safe_dump(lin.to_dict(), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# distribution.manifest  (the drift baseline)
# ---------------------------------------------------------------------------
def _is_distribution_owned(rel: Path) -> bool:
    """True if *rel* (relative to the profile root) is a distribution-owned file."""
    parts = rel.parts
    if not parts:
        return False
    if parts[0] in USER_OWNED:
        return False
    if rel.suffix.lower() in _JUNK_SUFFIXES:
        return False
    if rel.name in USER_OWNED:
        return False
    return True


def iter_owned_files(profile_dir: Path) -> List[Path]:
    """Sorted list of distribution-owned files, relative to the profile root."""
    root = Path(profile_dir)
    out: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if _is_distribution_owned(rel):
            out.append(rel)
    return sorted(out, key=lambda r: r.as_posix())


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_manifest(profile_dir: Path) -> Dict[str, str]:
    """Map of posix-relpath -> sha256 for every distribution-owned file."""
    root = Path(profile_dir)
    return {rel.as_posix(): _sha256(root / rel) for rel in iter_owned_files(root)}


def write_manifest(profile_dir: Path, manifest: Optional[Dict[str, str]] = None) -> Path:
    """Write distribution.manifest (sorted `path:sha256` lines) and return its path."""
    root = Path(profile_dir)
    m = manifest if manifest is not None else compute_manifest(root)
    lines = [f"{path}:{digest}" for path, digest in sorted(m.items())]
    out = root / MANIFEST_FILENAME
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out


def read_manifest(profile_dir: Path) -> Optional[Dict[str, str]]:
    p = Path(profile_dir) / MANIFEST_FILENAME
    if not p.is_file():
        return None
    out: Dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # rightmost ':' splits path from hex digest (paths never contain ':')
        path, _, digest = line.rpartition(":")
        if path and digest:
            out[path] = digest
    return out


@dataclass
class DriftReport:
    modified: List[str] = field(default_factory=list)   # in manifest, hash differs
    added: List[str] = field(default_factory=list)      # on disk, not in manifest
    removed: List[str] = field(default_factory=list)    # in manifest, gone from disk

    @property
    def clean(self) -> bool:
        return not (self.modified or self.added or self.removed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean": self.clean,
            "modified": self.modified,
            "added": self.added,
            "removed": self.removed,
        }


def compute_drift(profile_dir: Path) -> DriftReport:
    """Compare current distribution-owned files against distribution.manifest."""
    baseline = read_manifest(profile_dir)
    if baseline is None:
        raise FileNotFoundError(
            f"no {MANIFEST_FILENAME} in {profile_dir} — run 'manifest-gen' first"
        )
    current = compute_manifest(profile_dir)
    rep = DriftReport()
    for path, digest in sorted(current.items()):
        if path not in baseline:
            rep.added.append(path)
        elif baseline[path] != digest:
            rep.modified.append(path)
    for path in sorted(baseline):
        if path not in current:
            rep.removed.append(path)
    return rep


# ---------------------------------------------------------------------------
# LCA / merge-base over the lineage DAG
# ---------------------------------------------------------------------------
def _load_lineage_arg(spec: str) -> Lineage:
    """Load a Lineage from either a lineage.yaml path or a profile dir."""
    p = Path(spec)
    if p.is_dir():
        lin = read_lineage(p)
        if lin is None:
            raise FileNotFoundError(f"no {LINEAGE_FILENAME} in {p}")
        return lin
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Lineage.from_dict(data or {})


def _ancestor_set(lin: Lineage) -> Set[str]:
    """All ancestors of *lin* using its cached closure (edges + ancestry + roots).

    We include ``this`` so a node is considered its own ancestor (standard for
    merge-base: the LCA of A and a descendant-of-A is A).
    """
    names: Set[str] = {lin.this}
    names.update(lin.parent_names())
    names.update(lin.ancestry)
    names.update(lin.roots)
    return names


def lowest_common_ancestors(lins: Sequence[Lineage]) -> List[str]:
    """Names common to every input's ancestor set.

    With only cached closures (not the full DAG walk) this returns the set of
    *shared* ancestors; the caller treats the most-specific shared root as the
    merge base. For the common case (siblings forked from one baseline) this is
    exactly the baseline. Ordered from the inputs' ancestry for determinism.
    """
    if not lins:
        return []
    common = _ancestor_set(lins[0])
    for lin in lins[1:]:
        common &= _ancestor_set(lin)
    # Order by appearance in the first input's ancestry (root-first), then name.
    order = {name: i for i, name in enumerate(lins[0].ancestry)}
    return sorted(common, key=lambda n: (order.get(n, 10_000), n))


def merge_base(lins: Sequence[Lineage]) -> Optional[str]:
    """The single best merge base: the most-specific shared ancestor.

    'Most specific' = the shared ancestor that appears LAST in the first input's
    root->this ancestry chain (closest to the leaves). Falls back to any shared
    name, or None when the inputs share no ancestry.
    """
    common = lowest_common_ancestors(lins)
    if not common:
        return None
    chain = lins[0].ancestry + [lins[0].this]
    best = None
    for i, name in enumerate(chain):
        if name in common:
            best = name  # keep the last (deepest) match
    return best or common[-1]


# ---------------------------------------------------------------------------
# fork recording
# ---------------------------------------------------------------------------
def record_edge(
    child_dir: Path,
    this_name: str,
    event: str,
    parent: ParentEdge,
    event_reason: str = "",
    into: Optional["Lineage"] = None,
) -> Lineage:
    """Create or extend a child's lineage.yaml with one parent edge.

    Idempotent per parent name: re-recording the same parent updates that edge
    rather than duplicating it. Recomputes ``ancestry``/``roots`` from the
    parent's own lineage when reachable (parent.source local dir), else from the
    edge alone.

    For a multi-parent join, chain the calls by passing the previous return
    value as ``into`` — this accumulates parents in memory rather than
    re-reading the (not-yet-written) child dir between edges::

        lin = record_edge(d, "full", "join", ParentEdge(name="fe", ...))
        lin = record_edge(d, "full", "join", ParentEdge(name="be", ...), into=lin)
        write_lineage(d, lin)

    When ``into`` is None the child's on-disk ``lineage.yaml`` is used as the
    starting point (so a single call is still idempotent across process runs).
    """
    existing = into if into is not None else read_lineage(child_dir)
    if existing and existing.this == this_name:
        lin = existing
        lin.event = event or lin.event
        if event_reason:
            lin.event_reason = event_reason
    else:
        lin = Lineage(this=this_name, event=event, event_reason=event_reason)

    # upsert the parent edge
    lin.parents = [p for p in lin.parents if p.name != parent.name]
    lin.parents.append(parent)

    # recompute closure from parents' lineage where we can reach it
    ancestry: List[str] = []
    roots: List[str] = []
    for pe in lin.parents:
        p_lin = None
        if pe.source:
            src = Path(pe.source)
            if src.is_dir():
                p_lin = read_lineage(src)
        if p_lin:
            for a in p_lin.ancestry + [p_lin.this]:
                if a not in ancestry:
                    ancestry.append(a)
            for r in (p_lin.roots or [p_lin.this]):
                if r not in roots:
                    roots.append(r)
        else:
            if pe.name not in ancestry:
                ancestry.append(pe.name)
            if pe.name not in roots:
                roots.append(pe.name)
    lin.ancestry = ancestry
    lin.roots = roots or lin.parent_names()
    return lin


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_manifest_gen(args: argparse.Namespace) -> int:
    path = write_manifest(Path(args.profile_dir))
    m = read_manifest(Path(args.profile_dir)) or {}
    print(json.dumps({"wrote": str(path), "files": len(m)}, indent=2))
    return 0


def _cmd_drift(args: argparse.Namespace) -> int:
    rep = compute_drift(Path(args.profile_dir))
    print(json.dumps(rep.to_dict(), indent=2))
    return 0 if rep.clean else 1


def _cmd_show(args: argparse.Namespace) -> int:
    lin = read_lineage(Path(args.profile_dir))
    if lin is None:
        print(json.dumps({"lineage": None}, indent=2))
        return 1
    print(json.dumps(lin.to_dict(), indent=2))
    return 0


def _cmd_lca(args: argparse.Namespace) -> int:
    lins = [_load_lineage_arg(s) for s in args.lineages]
    print(
        json.dumps(
            {
                "merge_base": merge_base(lins),
                "shared_ancestors": lowest_common_ancestors(lins),
            },
            indent=2,
        )
    )
    return 0


def _cmd_record_fork(args: argparse.Namespace) -> int:
    parent = ParentEdge(
        name=args.parent,
        source=args.parent_source or "",
        version=args.parent_version or "",
        sha=args.parent_sha or "",
        at=args.at or "",
        reason=args.reason or "",
    )
    lin = record_edge(
        Path(args.child_dir),
        this_name=args.name,
        event=args.event,
        parent=parent,
        event_reason=args.event_reason or "",
    )
    path = write_lineage(Path(args.child_dir), lin)
    print(json.dumps({"wrote": str(path), "lineage": lin.to_dict()}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="lineage.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("manifest-gen", help="write distribution.manifest")
    p.add_argument("profile_dir")
    p.set_defaults(func=_cmd_manifest_gen)

    p = sub.add_parser("drift", help="report drift vs distribution.manifest")
    p.add_argument("profile_dir")
    p.set_defaults(func=_cmd_drift)

    p = sub.add_parser("show", help="print lineage.yaml summary")
    p.add_argument("profile_dir")
    p.set_defaults(func=_cmd_show)

    p = sub.add_parser("lca", help="lowest common ancestor / merge base")
    p.add_argument("lineages", nargs="+", help="lineage.yaml files or profile dirs")
    p.set_defaults(func=_cmd_lca)

    p = sub.add_parser("record-fork", help="append a lineage edge to a child")
    p.add_argument("child_dir")
    p.add_argument("--name", required=True, help="this profile's distribution name")
    p.add_argument(
        "--event",
        default="fork",
        choices=["fork", "split", "join", "repurpose", "root"],
    )
    p.add_argument("--event-reason", default="")
    p.add_argument("--parent", required=True, help="parent distribution name")
    p.add_argument("--parent-source", default="")
    p.add_argument("--parent-version", default="")
    p.add_argument("--parent-sha", default="")
    p.add_argument("--at", default="")
    p.add_argument("--reason", default="")
    p.set_defaults(func=_cmd_record_fork)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
