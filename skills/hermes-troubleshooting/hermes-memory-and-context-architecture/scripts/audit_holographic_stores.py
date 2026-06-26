#!/usr/bin/env python3
"""Audit holographic memory stores across all Hermes profiles.

Each profile has its OWN physically-separate SQLite store at
$HERMES_HOME/memory_store.db. This probe inventories every store: which
profiles have holographic configured, which have actually WRITTEN facts,
the per-store fact count, and the schema (so you can spot the memory_banks
partition lead).

Why python3 stdlib and not the `sqlite3` CLI: the sqlite3 binary is NOT
installed on every box (it wasn't on <main-host> as of 2026-06-16), but
python3's `sqlite3` module is always available. Prefer this probe over
`which sqlite3 && sqlite3 ...` so the audit works regardless of host.

Usage:
    python3 audit_holographic_stores.py            # default ~/.hermes home
    HERMES_HOME=/path python3 audit_holographic_stores.py

Read-only: opens every DB, counts, never writes. Does NOT print fact
CONTENT (intimate-lane stores like private-profile / companion-profile are
consent-sensitive — count only, never dump bodies).
"""
import os
import re
import sqlite3
import glob

HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))


def provider_for(config_path):
    """Read memory.provider out of a config.yaml without a YAML dep.

    NOTE: the provider key sits ~5 lines under the top-level `memory:` block,
    so a naive `grep -A3 '^memory:'` MISSES it. This state-machine walk over
    the top-level memory: block is the reliable read.
    """
    if not os.path.isfile(config_path):
        return "<no config>"
    in_memory = False
    try:
        with open(config_path) as f:
            for line in f:
                if re.match(r"^memory:", line):
                    in_memory = True
                    continue
                if in_memory:
                    m = re.match(r"^  provider:\s*(\S+)", line)
                    if m:
                        return m.group(1)
                    # left the top-level memory: block
                    if re.match(r"^[a-z]", line):
                        in_memory = False
    except Exception as e:
        return f"<err {e}>"
    return "<inherit/none>"


def count_facts(db_path):
    if not os.path.isfile(db_path):
        return None, None
    try:
        con = sqlite3.connect(db_path)
        tabs = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        cnt = "?"
        for t in ("facts", "fact", "memories", "memory"):
            if t in tabs:
                cnt = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                break
        con.close()
        return cnt, tabs
    except Exception as e:
        return f"ERR {e}", None


def main():
    homes = [("default", HOME)]
    for d in sorted(glob.glob(os.path.join(HOME, "profiles", "*"))):
        if os.path.isdir(d):
            homes.append((os.path.basename(d), d))

    print(f"{'PROFILE':24s} {'PROVIDER':16s} {'FACTS':>7s}  DB?")
    print("-" * 60)
    schema_seen = None
    for name, h in homes:
        provider = provider_for(os.path.join(h, "config.yaml"))
        db = os.path.join(h, "memory_store.db")
        cnt, tabs = count_facts(db)
        has_db = "yes" if os.path.isfile(db) else "NO (never written)"
        cnt_s = "-" if cnt is None else str(cnt)
        print(f"{name:24s} {provider:16s} {cnt_s:>7s}  {has_db}")
        if tabs and schema_seen is None:
            schema_seen = tabs

    if schema_seen:
        print("\nschema (all stores):", schema_seen)
        if "memory_banks" in schema_seen:
            print("  -> `memory_banks` present: investigate whether holographic")
            print("     supports bank-scoped partitioning (shared core + private")
            print("     satellites may be mostly config, not a build).")
    print(f"\nHERMES_HOME = {HOME}")
    print("Each row above is a PHYSICALLY SEPARATE SQLite file — no shared")
    print("memory across profiles by default. That isolation IS the topology.")


if __name__ == "__main__":
    main()
