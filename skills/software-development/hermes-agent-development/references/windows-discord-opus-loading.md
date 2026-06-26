# Windows Discord Opus Loading

## Problem

On Windows, Hermes's Discord adapter may log:

- `Opus codec not found — voice channel playback disabled`

...even when `discord.py` voice dependencies are installed.

## Root Cause

`discord.py` on Windows ships bundled Opus DLLs inside its package:

- `.../site-packages/discord/bin/libopus-0.x64.dll`
- `.../site-packages/discord/bin/libopus-0.x86.dll`

Upstream `discord.opus` auto-loads these bundled DLLs on Windows.

A Hermes adapter implementation that only calls `ctypes.util.find_library("opus")` bypasses the upstream Windows default and can falsely conclude that Opus is unavailable.

## Correct Fix

On `win32`, resolve Opus in this order:

1. Read `discord.opus.__file__`
2. Derive the sibling bundled DLL path under `discord/bin/`
3. Pick `libopus-0.x64.dll` for 64-bit Python or `libopus-0.x86.dll` for 32-bit Python
4. If the bundled DLL exists, load that path
5. Only on non-Windows, fall back to `ctypes.util.find_library("opus")` (plus macOS Homebrew fallback if needed)

## Why this is durable

This follows `discord.py`'s intended Windows loading behavior instead of depending on random system DLLs, game installs, or PATH accidents.

## Verification

- Direct resolver check should return the bundled DLL path on Windows
- Targeted test file: `tests/gateway/test_discord_opus.py`
- A real gateway restart should stop emitting `Opus codec not found — voice channel playback disabled` if this was the only blocker
