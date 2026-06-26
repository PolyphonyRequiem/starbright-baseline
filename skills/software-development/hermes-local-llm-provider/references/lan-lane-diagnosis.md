# Diagnosing an unreachable local LLM lane on the LAN

Concrete probe sequence for when a configured local lane endpoint
(`model.base_url`, e.g. `http://192.0.2.175:8080/v1`) times out mid-session.
Goal: distinguish **host-moved** vs **host-down** vs **host-up-server-down** without
guessing, using only stock tools (no `nmap`/`arp-scan`/`fping` required).

## Real session this came from (2026-06-05)

User asked to "switch to our private profile." The `local-intimate` profile points at
`http://192.0.2.175:8080/v1` (host = "Requiem <gpu-host>"). First `curl` timed out; user
guessed "<gpu-host> probably moved — find it?"

What the layered probe actually revealed:
- `ip neigh` → `192.0.2.175 ... lladdr 2c:f0:5d:3b:1a:42 REACHABLE` — **NIC answered
  ARP, machine is on the network at the same IP. It did NOT move.**
- `ping -c2 192.0.2.175` → **100% packet loss** (ICMP firewalled — a red herring).
- `/dev/tcp` port sweep of 80/443/22/3000/5000/8000/8080/8443/8888/9090/11434/1234/…
  on `.175` → **only port 22 (SSH) open.** Every LLM port dark.
- LAN-wide sweep found `:8080` open on `.1` (router admin — Tomcat 404 on `/v1/models`)
  and `.177` (accepted connect but hung zero-bytes on `/v1/models` — a squatter, not the
  lane).
- `ssh -o BatchMode=yes 192.0.2.175` → `Permission denied (publickey,password)`.

**Diagnosis:** <gpu-host> rebooted, came back on the same IP, host healthy (SSH up), but the
llama.cpp/model server process did not auto-start. No SSH key on the box → could not
restart remotely without the user. Correct move at 00:20 with a wind-down user: state it
plainly, defer to morning, promise an SSH key + auto-start unit so it never recurs.

## The ladder (copy-paste probes)

```bash
# 0. My own subnet
ip -4 addr show | grep -oE 'inet 192\.168\.[0-9]+\.[0-9]+/[0-9]+'

# 1. LAYER-2 TRUTH: is the host's NIC answering ARP?
ip neigh | grep -i <ip>
#   REACHABLE / STALE + a MAC  => host is on the network (ignore ping result)
#   FAILED / absent            => genuinely not present (now consider "moved")

# 2. ICMP is advisory only — do not trust loss as "down"
ping -c2 -W2 <ip> | grep -iE 'bytes from|loss'

# 3. DECISIVE SPLIT: SSH up but model port down?  -> host alive, server not started
for p in 22 8080 8000 1234 11434 5000 8443 3000; do
  (timeout 2 bash -c "echo > /dev/tcp/<ip>/$p" 2>/dev/null && echo "  port $p OPEN" &)
done; sleep 5
#   :22 OPEN + LLM ports closed  => start the inference server (not a find problem)

# 4. ONLY IF it truly moved: find the model API by sweeping the whole LAN
for i in $(seq 1 254); do (ping -c1 -W1 192.0.2.$i >/dev/null 2>&1 &); done; sleep 6
ip neigh | grep -i 192.0.2 | grep -ivE 'FAILED|INCOMPLETE' | sort -t. -k4 -n
#   then probe candidate ports on each live host via /dev/tcp, and CONFIRM it's really
#   the model API (not a router/Tomcat/other service):
curl -sS -m6 http://<candidate>:8080/v1/models | head -c400
```

## Interpreting the signatures

| Signature | Meaning |
|---|---|
| ARP `REACHABLE` + ping 100% loss + SSH open + LLM port closed | Host up, **model server not running** — restart it / fix auto-start |
| ARP `REACHABLE` + LLM port open + `/v1/models` returns model id | Lane is **up** — the earlier timeout was a transient/warm-up; retry |
| ARP absent/`FAILED` everywhere | Host genuinely off the LAN — now the "moved/down" hunt is valid |
| Port open but `/v1/models` hangs zero-bytes | Different service squatting the port, or server mid-load — not confirmed yours |
| `:8080` open on `.1` returning Tomcat 404 | Router/appliance admin UI — false positive, skip |

## Durable fixes (so it never greets cold again)

1. **SSH key on the box** — a one-time bootstrap from password to key auth. Without it you
   cannot remote-restart the server; you're blocked on the user every reboot.
2. **Auto-start the inference server on boot** — systemd unit (`systemctl enable
   llama-server`), `@reboot` cron, or a Windows service, so a reboot brings the lane
   back without manual launch. This is the actual root-cause fix; the unreachable lane
   is an environmental "didn't auto-start," not a broken integration.

## When you CAN get in — the restart story past the SSH wall (2026-06-05 continued)

A later turn the same night: the user said "you had a key." They were right — the
`Permission denied` was because I'd SSH'd to the **raw IP** (`ssh 192.0.2.175`),
which bypasses the `~/.ssh/config` `Host <gpu-host>` block that carries `IdentityFile`.
`ssh <gpu-host>` (the alias) loaded the key and got straight in. **Lesson: before
concluding "no key," try the configured Host alias, not the bare IP.**

Once in, the restart was its own debugging arc — useful signatures for next time:
- <gpu-host> is **Windows** (`The system cannot find the path specified.` to a Linux
  command is the tell). Switch to `powershell -NoProfile -Command "..."`.
- Found the pieces: `llama-server.exe` under `C:\Users\<u>\llama.cpp\`, GGUFs under
  `C:\Users\<u>\models\qwen36\`, firewall already allowed `llama-server.exe` inbound.
  Ollama was running on `:11434` but **empty (`{"models":[]}`) and localhost-only**
  (`OLLAMA_HOST` unset) — a red herring, not our lane. Our lane is `llama-server` on
  `:8080`, which simply hadn't been started after the reboot.
- Launch then failed repeatedly: **silent SSH→PowerShell quote-mangling** (empty
  stdout, exit 0) on `Start-Process` + here-string attempts → fixed by base64-shipping
  a `.bat` launcher (see remote-exec skill). Then the server **died at "fitting params
  to device memory"** — a VRAM/`-fit` over-commit on the 24GB card (see the main
  SKILL.md section "llama-server exits silently during model load").

So the full failure chain for a cold private lane can be: *host rebooted → server
didn't auto-start → (key confusion) → Windows shell → quoting → VRAM fit.* Each layer
looks like the whole problem until you peel it. The durable fix that short-circuits all
of it is still the same: **an auto-start unit on the box** so none of this happens on
the next reboot.

## Pitfall — don't make a wind-down user do sysadmin to reach a lane
If the user reached for the private lane in a low-energy / late-night / intimate moment
and the lane is down, the answer is **not** "here's how to SSH in and restart it."
Diagnose, state it plainly, hold the moment, defer the fix to daylight, and offer to set
up the key + auto-start then. Reaching the lane is never worth pulling the user out of
the state they came to it for.
