#!/usr/bin/env python3
"""reconcile.py — 3-way merge classifier for profile joins and drift-aware updates.

Given a merge BASE and two SIDES (ours/theirs — or parent-A/parent-B for a
join), classify every distribution-owned file by how it changed on each side,
using the sha256 hashes from profile-lineage. The output tells the agent
exactly which files are auto-resolvable and which are TRUE CONFLICTS needing a
human/agent decision — so the agent never blind-picks.

This is the shared engine behind two callers:
  * profile-reconcile — merging 2+ parents into a joined profile.
  * drift-aware update — pulling upstream into a locally-drifted fork
                         (base=fork point, ours=local edits, theirs=upstream).

Classification per path (base B, ours O, theirs T are sha256 or None=absent):
    both-absent            impossible (path came from a union of sides)
    unchanged              O == T                      -> trivial, take either
    ours-only              O != B, T == B              -> auto-take ours
    theirs-only            T != B, O == B              -> auto-take theirs
    same-edit              O == T != B                 -> convergent, take either
    add-ours / add-theirs  added on exactly one side   -> auto-take that side
    add-both-same          added both, identical       -> take either
    conflict               O != T and both differ from B (or add-both-differ,
                           or edit-vs-delete)          -> TRUE CONFLICT

CLI:
    reconcile.py classify --base B/ --ours O/ --theirs T/    # dirs (auto-hash)
    reconcile.py classify --base-manifest b.manifest \\
                          --ours-manifest o.manifest \\
                          --theirs-manifest t.manifest
Prints JSON: {auto: {...}, conflicts: [...], summary: {...}}. Exit 0 when there
are zero conflicts, 1 when conflicts remain (so bash can gate on it).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lineage as L  # noqa: E402  (sibling module in the same scripts/ dir)


@dataclass
class Classified:
    auto: Dict[str, str] = field(default_factory=dict)      # path -> resolution
    conflicts: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        kinds: Dict[str, int] = {}
        for res in self.auto.values():
            kinds[res] = kinds.get(res, 0) + 1
        return {
            "auto": self.auto,
            "conflicts": self.conflicts,
            "summary": {
                "auto_count": len(self.auto),
                "conflict_count": len(self.conflicts),
                "auto_kinds": kinds,
            },
        }


def classify(
    base: Dict[str, str],
    ours: Dict[str, str],
    theirs: Dict[str, str],
) -> Classified:
    """Classify the union of paths across the three manifests."""
    out = Classified()
    paths = sorted(set(base) | set(ours) | set(theirs))
    for p in paths:
        b = base.get(p)
        o = ours.get(p)
        t = theirs.get(p)

        if o == t:
            # identical on both sides (incl. both-absent, both-added-same,
            # both-deleted, or neither touched) — nothing to decide.
            if o is not None:
                out.auto[p] = "unchanged" if o == b else "same-edit"
            continue

        # o != t below
        if b is None:
            # added on one or both sides, differently
            if o is None:
                out.auto[p] = "add-theirs"
            elif t is None:
                out.auto[p] = "add-ours"
            else:
                out.conflicts.append(_c(p, b, o, t, "add-both-differ"))
            continue

        # base present, sides differ
        if o == b:
            out.auto[p] = "theirs-only" if t is not None else "delete-theirs"
        elif t == b:
            out.auto[p] = "ours-only" if o is not None else "delete-ours"
        else:
            # both sides diverged from base in different ways
            if o is None or t is None:
                out.conflicts.append(_c(p, b, o, t, "edit-vs-delete"))
            else:
                out.conflicts.append(_c(p, b, o, t, "edit-vs-edit"))
    return out


def _c(path, b, o, t, kind) -> Dict[str, str]:
    return {
        "path": path,
        "kind": kind,
        "base": b or "",
        "ours": o or "",
        "theirs": t or "",
    }


def _manifest_from_dir(d: str) -> Dict[str, str]:
    return L.compute_manifest(Path(d))


def _manifest_from_file(f: str) -> Dict[str, str]:
    m = L.read_manifest(Path(f).parent) if Path(f).name == L.MANIFEST_FILENAME else None
    if m is not None:
        return m
    # generic path:sha reader for an arbitrary manifest file
    out: Dict[str, str] = {}
    for line in Path(f).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path, _, digest = line.rpartition(":")
        if path and digest:
            out[path] = digest
    return out


def _cmd_classify(args: argparse.Namespace) -> int:
    if args.base_manifest:
        base = _manifest_from_file(args.base_manifest)
        ours = _manifest_from_file(args.ours_manifest)
        theirs = _manifest_from_file(args.theirs_manifest)
    else:
        base = _manifest_from_dir(args.base)
        ours = _manifest_from_dir(args.ours)
        theirs = _manifest_from_dir(args.theirs)
    res = classify(base, ours, theirs)
    print(json.dumps(res.to_dict(), indent=2))
    return 0 if not res.conflicts else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="reconcile.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("classify", help="3-way classify base/ours/theirs")
    p.add_argument("--base")
    p.add_argument("--ours")
    p.add_argument("--theirs")
    p.add_argument("--base-manifest")
    p.add_argument("--ours-manifest")
    p.add_argument("--theirs-manifest")
    p.set_defaults(func=_cmd_classify)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "classify":
        dir_mode = args.base and args.ours and args.theirs
        man_mode = args.base_manifest and args.ours_manifest and args.theirs_manifest
        if not (dir_mode or man_mode):
            sys.stderr.write(
                "classify needs either --base/--ours/--theirs dirs or all three "
                "--*-manifest files\n"
            )
            return 2
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
