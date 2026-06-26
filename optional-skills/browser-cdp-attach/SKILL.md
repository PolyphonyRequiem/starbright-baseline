---
name: browser-cdp-attach
description: Attach to the user's real Chrome/Edge via Chrome DevTools Protocol when headless browsing hits SSO bot detection, self-signed certs, or you need their existing logged-in cookies. Class-level pattern, not site-specific.
version: 1.0.0
author: Starbright
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [browser, chrome, edge, cdp, automation, sso, bot-detection]
    related_skills: [node-inspect-debugger, google-workspace, unifi-controller-api]
---

# Browser CDP attach — drive the user's real browser

## When to load

Any time a "use the browser" task hits one of these walls:

- **SSO bot detection.** Headless Chromium fingerprints (Ubiquiti, Cloudflare-protected sites, Google sign-in with risk signals, Microsoft accounts, banks) silently disable the submit button on click. No toast, no error, no console output — the form just refuses.
- **Anti-scraping walls on retail / consumer sites.** DataDome, PerimeterX/HUMAN, Akamai Bot Manager, Cloudflare Turnstile — common on Anthropologie, Aerie, Levi's, Madewell, Nike, ticketing, sneakers, airline pricing. Symptom: `curl` returns 403, headless browser lands at "Access Denied" / DataDome captcha frame, and the page never renders product data. **Do NOT reach for self-hosted scraping infra (Firecrawl, SearXNG, Playwright stealth) first** — those use the same headless fingerprint and get blocked too. CDP-attach to the user's real browser is usually the right move *if* the user's existing profile has organic browsing history with that site (cookies, completed-CAPTCHA marker, behavioral signals). **However:** a freshly-installed Chrome with a brand-new `--user-data-dir` will STILL get DataDome-blocked even with `--disable-blink-features=AutomationControlled` on a real X11 display — DataDome scores session history + canvas/font fingerprint + behavior, not just the `webdriver` flag. Confirmed 2026-06-01: user-space Chrome 148 with a fresh profile hit the same CAPTCHA iframe as headless. **When the user's existing profile isn't available, route around the block instead of trying to defeat it** — for retail specifically, Google Lens reverse-image search (`the partner-fit-finder` → `references/google-lens-upload.md`) surfaces the same retailer's PDPs as Google result cards without touching the brand directly.
- **Self-signed cert without a flag knob.** Local infra UIs (UniFi at `https://192.0.2.1`, NAS controllers, internal dashboards) return `net::ERR_CERT_AUTHORITY_INVALID` and the Hermes `browser_navigate` wrapper does not expose `--ignore-https-errors` to the agent.
- **Need existing cookies/sessions.** "Pull the UniFi MFA code from my inbox" or "click through the wizard I'm already logged into" — re-authing from a fresh profile is slow and triggers more bot checks than it bypasses.
- **OAuth-not-set-up fallback.** API-based access (Gmail via `google-workspace`, etc.) would be cleaner but the user hasn't run setup yet and doesn't want to right now. CDP attach is the "right now" answer.

If the task is read-only and a documented API exists with auth already configured, prefer the API. CDP attach is for when the API path is blocked, missing, or would require ~5+ min of user setup the user hasn't agreed to.

## The pattern (Windows + Edge)

Windows-only — but `chrome.exe` works identically. On macOS/Linux substitute the binary path.

```bash
# 1. Find the browser binary
where chrome.exe 2>&1
find '/c/Program Files (x86)/Microsoft/Edge/Application' -iname '*.exe' 2>/dev/null | head -5

# 2. List running instances — Chromium enforces single-instance-per-profile,
#    so any existing process must be killed or the --remote-debugging-port flag
#    is silently ignored when the new launch forwards to the existing instance.
tasklist //FI "IMAGENAME eq msedge.exe" 2>&1 | head -10

# 3. Kill all existing instances. Warn the user this will close their tabs —
#    Edge/Chrome restore-on-relaunch is on by default but not guaranteed.
taskkill //F //IM msedge.exe; sleep 2

# 4. Relaunch with --remote-debugging-port AND --user-data-dir pointing at
#    the REAL profile path. Without --user-data-dir Chromium spawns a blank
#    profile with no cookies, which defeats the entire point.
#    --restore-last-session reopens the tabs the user had.
'/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' \
  --remote-debugging-port=9222 \
  --user-data-dir="C:\\Users\\<winuser>\\AppData\\Local\\Microsoft\\Edge\\User Data" \
  --restore-last-session &

# 5. Verify CDP is up
sleep 3 && curl -sS http://127.0.0.1:9222/json/version | head -10
# expect: {"Browser":"Edg/...","webSocketDebuggerUrl":"ws://..."}

# 6. Hand the connection to agent-browser
cd /path/to/hermes-agent && ./node_modules/.bin/agent-browser connect 9222
# expect: "✓ Done"
```

After step 6, `browser_navigate` / `browser_click` / etc. operate against the real browser. Gmail, internal SSO, locked-down corporate dashboards — all logged-in already.

## Default profile paths

| OS | Browser | Default `--user-data-dir` |
|---|---|---|
| Windows | Edge | `C:\Users\<user>\AppData\Local\Microsoft\Edge\User Data` |
| Windows | Chrome | `C:\Users\<user>\AppData\Local\Google\Chrome\User Data` |
| macOS | Chrome | `~/Library/Application Support/Google/Chrome` |
| macOS | Edge | `~/Library/Application Support/Microsoft Edge` |
| Linux | Chrome | `~/.config/google-chrome` |
| Linux | Chromium | `~/.config/chromium` |

If the user has multiple profiles, the `Default` subdirectory is the first one; named profiles look like `Profile 1`, `Profile 2`. Pass the *parent* `User Data` path (Chromium picks the last-used profile from there) unless the user specifies otherwise.

## Privilege escalation — STOP AND ASK

CDP attach gives you the user's full authenticated browser. That includes:
- their email (read AND write)
- saved passwords (autofill prompts you trigger)
- banking / health / private accounts in other tabs
- session cookies for everything they're logged into

**Before any non-read action**, confirm with the user. The right pattern:

> "I'm now driving your real browser — I have access to your full Gmail, plus
> any other site you're logged into. I'll only read MFA codes / navigate
> public pages. If I need to send mail, archive, delete, click 'allow' on a
> permissions dialog, or submit a form that costs money — I'll ask first.
> OK?"

If the API-based alternative exists (e.g., `google-workspace` with OAuth scopes) and the user is OK with a one-time 5-min setup, **offer it as the cleaner path** before continuing with CDP. OAuth is auditable + revokable in one click; CDP is "fox in the henhouse" by design.

## Pitfalls

- **`hermes browser_navigate` (the Python wrapper) cannot directly use a CDP URL** — you must `agent-browser connect <port>` from the CLI first, then `browser_navigate` operates against the connected session. Trying `browser_navigate cdp:http://127.0.0.1:9222` returns "Cannot navigate to invalid URL."
- **MCP `browser_navigate` may spawn a fresh blank tab instead of reusing the CDP session.** After a successful `agent-browser connect 9222 → ✓ Done`, calling `browser_navigate https://mail.google.com/...` from the MCP wrapper can land at `about:blank` or open a new tab without the user's cookies, defeating the attach. **Workaround: drive `agent-browser` directly from `terminal` instead** — `agent-browser --cdp 9222 <subcommand>` is the durable form that reliably acts on the already-attached browser. Use the MCP tools for navigation in the connected tab only after confirming via `agent-browser --cdp 9222 get url` that you're on the page you expect.
- **`agent-browser connect` blocks if you pass a full URL** — `agent-browser connect http://127.0.0.1:9222` timed out in testing; `agent-browser connect 9222` (just the port) returned cleanly. Use the port form.
- **Single-instance lock.** If you skip the `taskkill` step, the relaunch silently forwards to the running instance and CDP is NOT enabled. `curl http://127.0.0.1:9222/json/version` will fail to connect. Always kill first.
- **`--user-data-dir` mismatch loses logins.** If you point at a fresh path (or omit it), the browser launches signed out. The user will see Gmail asking them to log in — that's the symptom of a wrong profile path.
- **Other Chromium browsers also speak CDP.** Brave, Vivaldi, Opera, Arc all accept `--remote-debugging-port`. Same trick, different binary path.
- **Multiple debug ports collide.** If you already have a CDP-enabled browser running on 9222 (e.g., Hermes auto-launched Chrome earlier), choose a different port like 9223 — don't kill the existing instance unless you're sure it isn't carrying agent state.
- **Existing-browser cleanup.** When you're done, do NOT kill the user's relaunched browser — they're using it for their actual work. Just let it run. The CDP port stays open until they close the browser themselves.

## Verifying the attach worked

After `agent-browser connect 9222 → "✓ Done"`, navigate to any logged-in page (`https://gmail.com`, `https://github.com`, etc.) — if it lands at the inbox / dashboard, the profile carried. If it lands at a sign-in page, you got the profile path wrong; kill the browser, fix the path, relaunch.

```bash
# Quick visual check
agent-browser open https://mail.google.com/mail/u/0/
agent-browser snapshot | head -20
# Looking for: inbox UI, user avatar, list of messages. NOT a "Sign in" form.
```

## Working with the user's existing tabs

When the user already has a tab open with the thing you need — e.g. a UniFi cloud UI session already authenticated, a Gmail inbox, an in-progress wizard — switching to that tab is much cleaner than opening fresh. CDP exposes all open pages via `--cdp <port>`.

```bash
# List all live tabs across the connected browser (numbered as t1, t2, …)
agent-browser --cdp 9222 tab list

# Look for the title you want:
#   [t15] MFA Login Authentication - the user@<user-domain> - ... Mail - https://mail.google.com/...
#   [t20] requiem DreamRouter 7 - UniFi Network - https://unifi.ui.com/...

# Switch — IMPORTANT: pass the `t<N>` label, not the bare integer
agent-browser --cdp 9222 tab t15
#   ✓ MFA Login Authentication - the user@<user-domain> - ...

# Now the rest of the CLI operates on that tab
agent-browser --cdp 9222 get url
agent-browser --cdp 9222 eval 'location.href'
```

`agent-browser --cdp 9222 tab 15` (no `t` prefix) errors with `Expected a tab id like t15 or a label; positional integers are not accepted`. Always use the `t<N>` form.

You're also seeing the user's full browsing surface here — Reddit tabs, Hulu, banking sessions, dev consoles for other accounts. Don't poke any of it. Stick to the tabs that match the task.

## Extracting MFA codes from Gmail (or any web mail)

A common motivation for CDP attach is "the user can't be on screen to paste me a one-time code." Pattern:

```bash
# 1. Navigate the connected tab to a narrow search
agent-browser --cdp 9222 open 'https://mail.google.com/mail/u/0/#search/from%3Aubiquiti+newer_than%3A1h'
# Or, if there's already a relevant tab, switch to it with `tab t<N>`

# 2. The inbox lists conversations but not bodies. Click the top row to expand:
agent-browser --cdp 9222 eval 'document.querySelector("tr.zA").click(); "expanded"'
sleep 2

# 3. Pull the code from the rendered body. Use a regex that's narrow enough to
#    avoid false positives (other 6-digit strings happen):
agent-browser --cdp 9222 eval '
  var t = document.body.innerText;
  var matches = [];
  var re = /verification code is:?\s*(\d{6})|^\s*(\d{6})\s*$/gim;
  var m; while ((m = re.exec(t))) matches.push(m[1] || m[2]);
  var times = t.match(/\d{1,2}:\d{2}\s*(AM|PM)/gi);
  JSON.stringify({codes: matches, times: times})
'
# → {"codes":["819657","165378","329509"],"times":["9:33 AM","9:57 AM","10:22 AM"]}
```

Take the **newest** code (last in the array, latest timestamp). Gmail collapses old codes in the same thread, so multiple appear — using a stale one will trip the SSO's "invalid credentials" rate-limit response, which then makes you wait ~30s before retrying. Always use the freshest.

If the thread is collapsed and `innerText` only shows the subject + sender, you need to click the row first (as in step 2). The `tr.zA` selector is Gmail's conversation row class — stable across redesigns as of 2026.

## When NOT to use this

- If the user is sitting in front of the machine *right now* and can paste a code in 10 seconds — just ask. CDP attach disrupts their browser session (taskkill + relaunch). Faster + politer to ask for the code.
- If a documented, scoped API exists and is set up (or could be set up in <5 min the user agrees to). OAuth is always cleaner than CDP for recurring tasks.
- If the action you need to take is destructive or sensitive (send email, delete files, make payments, change account settings). Even with permission, do this through narrower-scope tooling when possible.

## Class structure

This skill is the umbrella for any "drive the user's real browser" pattern. Site-specific quirks (bot-detection behavior on a particular SSO, profile-path gotchas for a specific OS install) go under `references/<site-or-os>.md`.

Related: `node-inspect-debugger` covers CDP for *debugging Node.js processes* — same protocol, very different use case.
