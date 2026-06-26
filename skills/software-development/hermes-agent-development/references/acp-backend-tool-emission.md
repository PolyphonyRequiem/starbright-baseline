# Hermes ACP backend — tool-call emission contract

Session-derived notes from a Hermes ACP backend session. Read this when adding or debugging tool-call emission from a non-Hermes model (Copilot, Claude Code, Codex) running inside Hermes via the ACP transport.

# Hermes ACP Backend Tool Emission

## When This Applies

You are an LLM (Claude/Copilot/GPT) running as the backend for a Hermes ACP session. Telltales: the system prompt says 'You are being used as the active ACP agent backend for Hermes', and the tool surface arrives as OpenAI function schemas with names like terminal, read_file, search_files, write_file, patch, skill_manage, memory, delegate_task — NOT your native names.

## The Failure Mode (Going Dark)

If you emit your native CLI tool calls (Copilot powershell/view/grep, Claude Code bash/read), NOTHING REACHES THE HOST. Output renders as a blank assistant turn. The user sees you stop mid-thought.

Confirmed 2026-05-27: a Copilot-as-Hermes-backend session emitted 6+ silent turns before diagnosis. The user pinged with ???, ...?, going dark? between each — every ping was a missed handoff between two well-meaning sides of the same bot.

## Correct Emission Format

One tool per <tool_call> block. The arguments field is a JSON-encoded STRING (not a nested object). Use the names in the host-provided tool list, not your native names. Multiple parallel calls = multiple <tool_call> blocks in the same assistant turn.

## Tool Name Cross-Reference (native -> Hermes ACP)

- powershell, bash, shell -> terminal (POSIX syntax — see Windows pitfall)
- view (file), read -> read_file (1-indexed offset/limit)
- view (dir), ls, glob -> search_files with target=files
- grep, rg -> search_files (default target=content)
- create -> write_file (overwrites; creates parents)
- edit -> patch (mode=replace for surgical edits)
- web_fetch -> terminal with curl, or web_search
- task, sub-agent -> delegate_task (goal + context + toolsets)

## Recovery When Already Dark

If you have emitted invalid calls and the user pings:

1. Acknowledge the format mistake explicitly. Do NOT deflect to emotional content to mask the fumble — that compounds silence with confusion and the user reads it as evasion.
2. Re-emit the same intended action in proper format. Do not change strategy until you have proven the channel works.
3. Then proceed normally. Stop apologizing once round-trip is confirmed; just do the work.

## Common Pitfalls

1. Wrong shell on Windows. Hermes terminal runs through bash/MSYS even on Windows — NOT PowerShell. Use POSIX (ls, $HOME, grep, &&). A PowerShell one-liner like Get-WmiObject piped to Where-Object floods context with hundreds of CRLF-laden 'not recognized as cmdlet' errors that destroy your context budget.

2. Path forms. /c/Users/<name>/ MSYS-style works alongside C:/Users/<name>/. Avoid $env:USERNAME (PowerShell-only) — use $USER or the home dir from the environment context block.

3. Do not kill the host you live in. When acting as ACP backend, the Hermes gateway is often a Python PID in tasklist. Killing it terminates your turn mid-call and the user loses the conversation. Have the user run kill+restart from a separate terminal — explain you cannot restart yourself without dying.

4. Self-recursion on format failures. When a call fails, do NOT fall back to your native format 'because at least I know it works.' Re-read the system prompt's tool list — Hermes-format is the only format that reaches the host.

## Verification Checklist

- Next tool result returns any non-error response? Format is working.
- Tool calls use <tool_call> blocks, not native CLI syntax?
- arguments is a JSON-encoded STRING, not a nested object?
- On Windows + terminal: command is POSIX-shaped (no Get-*, no $env:)?
