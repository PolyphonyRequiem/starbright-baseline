#!/usr/bin/env python3
"""Probe the live GitHub Copilot model catalog through Hermes auth.

Prints every model the current Copilot credential can route to, with
context window, output cap, supported reasoning levels, thinking
budgets, and capability flags.

Run inside the hermes-agent venv:
    cd ~/.hermes/hermes-agent && source venv/bin/activate
    python3 ~/.hermes/skills/hermes-troubleshooting/hermes-model-catalog-introspection/scripts/probe_copilot_catalog.py

Filter to a substring with one positional arg:
    python3 probe_copilot_catalog.py sonnet
    python3 probe_copilot_catalog.py 4.8
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def main(filter_substr: str | None = None) -> int:
    try:
        from hermes_cli.copilot_auth import (
            copilot_request_headers,
            get_copilot_api_token,
            resolve_copilot_token,
        )
    except ImportError as exc:
        print(f"ERROR: hermes_cli not importable — activate the hermes-agent venv first ({exc})", file=sys.stderr)
        return 2

    gh_tok_pair = resolve_copilot_token()
    gh_tok = gh_tok_pair[0] if isinstance(gh_tok_pair, tuple) else gh_tok_pair
    if not gh_tok:
        print("ERROR: no Copilot/gh token available — run `hermes login` or `gh auth login`", file=sys.stderr)
        return 3

    api_tok = get_copilot_api_token(gh_tok)
    headers = copilot_request_headers()  # kwargs-only signature
    headers["Authorization"] = f"Bearer {api_tok}"

    req = urllib.request.Request("https://api.githubcopilot.com/models", headers=headers)
    try:
        body = urllib.request.urlopen(req, timeout=15).read()
    except urllib.error.HTTPError as exc:
        print(f"ERROR: HTTP {exc.code} from Copilot catalog: {exc.read()[:300]!r}", file=sys.stderr)
        return 4

    catalog = json.loads(body)
    rows = catalog.get("data", [])
    if filter_substr:
        rows = [m for m in rows if filter_substr.lower() in str(m.get("id", "")).lower()]

    if not rows:
        print(f"no models matched filter {filter_substr!r}")
        return 1

    for m in sorted(rows, key=lambda r: r.get("id", "")):
        mid = m.get("id", "?")
        name = m.get("name", "")
        caps = m.get("capabilities", {})
        lim = caps.get("limits", {})
        sup = caps.get("supports", {})
        ctx = lim.get("max_context_window_tokens", "?")
        out = lim.get("max_output_tokens", "?")
        reasoning = sup.get("reasoning_effort") or "—"
        thinking = sup.get("adaptive_thinking", False)
        max_think = sup.get("max_thinking_budget", "—")
        vision = sup.get("vision", False)
        tools = sup.get("tool_calls", False)
        print(f"{mid}")
        print(f"  name:      {name}")
        print(f"  context:   {ctx}    output: {out}")
        print(f"  reasoning: {reasoning}")
        print(f"  thinking:  adaptive={thinking}  max_budget={max_think}")
        print(f"  features:  vision={vision}  tool_calls={tools}")
        print()

    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(main(arg))
