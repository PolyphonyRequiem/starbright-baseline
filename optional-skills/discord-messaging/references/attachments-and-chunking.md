# Attachments and Chunking

Two recurring patterns that don't fit the basic send/read flows.

## Uploading Attachments via REST (multipart)

`send_message` only sends text. To upload files (images, audio, arbitrary
binaries) to a Discord channel, POST multipart/form-data to the messages
endpoint yourself. The response includes the full message object, whose
`attachments[].url` field is the **public Discord CDN URL** for the uploaded
file — useful both as a sharable link and as an HTTP URL for any other tool
that needs `https://...` rather than a local path.

```bash
set -a && source ~/.hermes/.env && set +a

# Upload one file. -F repeats per file for multi-attach (max 10 per message).
curl -s -X POST "https://discord.com/api/v10/channels/<channel_id>/messages" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -F "payload_json={\"content\": \"optional caption\"}" \
  -F "files[0]=@/c/Users/<you>/path/to/image.png"
```

Parse `attachments[0].url` from the JSON response to get the CDN URL. The
URL contains a signed `ex=`/`is=`/`hm=` query string — those are required
for the URL to fetch publicly. Don't strip them.

**File size cap:** 25 MB for bots without Nitro boost (server-dependent).
Larger files return `Request entity too large (413)` — downsize first.

**Use cases for the returned CDN URL:**
- Re-embed the same image elsewhere in markdown without re-uploading.
- Feed it to any tool expecting `https://...` for an image source (some
  tools reject local file paths but accept public HTTP URLs).
- Share an external-facing link to a file you only had locally.

## Chunking Long Messages With Per-Chunk Spoiler Tags

Discord caps messages at **2000 characters**. For long content (erotic
fiction, multi-page drafts, large quotes), you must chunk. Two pitfalls:

### Pitfall: spoiler tags don't span message boundaries

`||spoiler||` only hides text within a single message. If you split a long
spoilered passage across N messages by putting `||` at the very start of
message 1 and `||` at the very end of message N, **only message 1 will be
spoilered** — messages 2..N render as plain unhidden text. This is the
classic mistake that leaks NSFW content to anyone scrolling.

**Fix:** wrap each chunk individually in its own `||...||` pair, so every
message is self-contained as a spoiler.

```
Chunk 1: ||...text of chunk 1...||
Chunk 2: ||...text of chunk 2...||
...
Chunk N: ||...text of chunk N...||
```

### Pitfall: spoiler markers themselves count toward 2000 chars

When chunking, account for the 4 chars (`||` + `||`) plus any chunk-marker
prefix (`**Chunk 3/8**\n\n`). Aim for ~1900-char body content to leave room.

### Sequencing

Send chunks one at a time, in order, via `send_message`. Discord generally
preserves order from the same bot if requests are serialized, but parallel
posts can interleave — don't fire them concurrently when order matters.

### Markdown that crosses chunk boundaries

Bold/italic/strikethrough markers (`**...**`, `*...*`, `~~...~~`) also do
not span messages. If a markdown-emphasized passage runs across a chunk
break, either close-and-reopen on both sides or move the break to a
paragraph boundary where no markup is open.

## Verification Checklist

After chunked delivery of sensitive content:

1. Open the channel as a different user (or in incognito if testing).
2. Confirm **every** chunk shows the blurred spoiler bar, not just the first.
3. Tap one mid-sequence chunk to confirm the spoiler reveal works on its own.
4. If any chunk renders unblurred, you mis-wrapped — delete the leaked
   message immediately, then repost that chunk with proper `||...||` around
   the whole body.
