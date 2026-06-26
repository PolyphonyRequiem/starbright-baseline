# Discord Voice Receive — Hook-vs-Websocket Lifecycle Bug

## Symptom

Confirmed 2026-05-28 on `hermes_plugins/discord_platform/adapter.py`:

User runs `/voice join` (and optionally `/voice on`) in a guild voice
channel. Gateway log shows the bot connecting successfully:

```
[Discord] slash '/voice join' invoked by user=…
Speaking hook installed on live websocket
VoiceReceiver started (bot_ssrc=…)
SPEAKING event: ssrc=… -> user=<user-id-A>
SPEAKING event: ssrc=… -> user=<user-id-B>
```

…and then **nothing follows**. No `Voice input from user N: <transcript>`
lines. No `Playing TTS in voice channel` follow-ups. The bot is sitting
in the channel, sees that people are speaking (SPEAKING events keep
arriving), but never produces a transcript or a reply.

A `/restart` of the gateway clears it. Voice works again on a fresh
join.

## Why

`Speaking hook installed on live websocket` (in the adapter's voice
join path) attaches a hook to **whichever VoiceClient websocket is
live at that exact moment**. Two things can recycle that websocket:

- **Channel moves.** When the bot is asked to follow a user into a
  different voice channel (or when the user moves and the bot is
  configured to follow), Discord spins up a new voice ws for the new
  channel.
- **Voice region / reconnect events.** Even without a channel change,
  Discord can swap the voice ws (region change, transient disconnect,
  server-side failover).

When the underlying ws is replaced:

- The **gateway-level SPEAKING event listener** still fires from the
  new ws — that's why the `SPEAKING event: ssrc=… -> user=…` log lines
  keep showing up.
- The **audio decoder / VoiceReceiver** is still bolted to the *old*
  ws. Packets land on the new ws and never reach the decoder. STT
  pipeline is starved; no transcripts; no reply.

The misleading part of the bug is exactly that the speaking events
keep flowing — it looks like the bot is hearing people. It isn't. The
log line you should look for is `Voice input from user N: <transcript>`
— if that's absent for >5 seconds after a SPEAKING event for a user
who is actively talking, the receiver is bound to a dead ws.

## Diagnostic recipe

```bash
LOG=~/.hermes/logs/gateway.log
# Walk the most recent voice join through the next 60 seconds.
grep -niE 'voice|opus|stt|tts|wsproto|websocket|closed' "$LOG" | tail -120

# Specifically check for the "hook installed once, never re-installed"
# pattern around a channel move:
grep -niE "Speaking hook|VoiceReceiver|Voice state.*moved|Voice input from user" "$LOG" | tail -60
```

Healthy session looks like:

```
Speaking hook installed on live websocket
VoiceReceiver started
…
Voice input from user 373996…: Hello, Starbright. Are you able to hear me?
Playing TTS in voice channel
```

Broken session looks like:

```
Speaking hook installed on live websocket
VoiceReceiver started
…
Voice state: <user> moved Sleep Call -> General (guild …)   # ws was replaced
SPEAKING event: ssrc=… -> user=…                            # new ws talks
SPEAKING event: ssrc=… -> user=…
# … no Voice input lines, no TTS playback …
```

Note: the `Voice state: X moved` line for *the bot's own channel*
(not just a user's) is the load-bearing signal. A user moving into
the bot's channel doesn't replace the bot's ws; the bot moving (or
following) does.

## The fix (sketch)

The adapter currently installs the speaking hook and starts the
VoiceReceiver once at `/voice join` time. It needs to re-do both on
ws replacement. Two events to hook:

1. **`on_voice_state_update` for the bot's own user.** When `before.channel
   != after.channel` and the user is `self.user`, the bot just moved
   between channels — its voice ws is being replaced. Tear down and
   restart the receiver pointed at the new VoiceClient's ws, and
   re-install the speaking hook.
2. **VoiceClient ws reconnect.** When discord.py reconnects the voice
   ws under the same VoiceClient (e.g. region change), the same
   teardown/restart is needed. The cleanest place to intercept is a
   wrapper around `VoiceClient.connect` / the internal `_connect_to_id`
   that re-emits a "ws replaced" event the adapter can listen for.

Pseudo-pattern:

```python
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id != bot.user.id:
        return
    if before.channel is not None and before.channel != after.channel:
        # Bot moved. Tear down the old receiver, rebind to the new ws.
        await _restart_voice_receiver(after.channel.guild)

async def _restart_voice_receiver(guild):
    vc = guild.voice_client
    if vc is None or not vc.is_connected():
        return
    await _stop_voice_receiver(guild)
    _install_speaking_hook(vc.ws)
    _start_voice_receiver(vc)
```

The teardown half (`_stop_voice_receiver`) must (a) cancel any audio
decode tasks pinned to the old ws, (b) close the old SSRC→user map so
the new ws's SSRC numbering isn't aliased onto stale users.

## Don't try

- **Don't busy-poll the ws.** A retry loop that pings the ws every
  second hides the bug instead of fixing it and racks up CPU.
- **Don't restart the entire VoiceClient.** That kicks the bot out of
  the channel and back in — visible to users, and it still doesn't
  fix the underlying lifecycle issue if it recurs on the next move.
- **Don't add an arbitrary `await asyncio.sleep(N)` before
  `_install_speaking_hook`.** The race isn't time-based; it's
  event-based. Hook into the events.

## Related

- `hermes-agent-development` SKILL.md pitfall on Discord voice
  receiver rebinding — that's the user-facing pointer to this file.
- `hermes-voice-mode` skill (`hermes-troubleshooting/`) covers
  end-user voice setup and STT/TTS provider tuning; this file is
  about the adapter-level lifecycle bug behind a specific failure
  mode end-users see as "voice chat just stopped working."
