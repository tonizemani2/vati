# Capture / agent chat deploy plan (HOLD — ship only on explicit go)

Goal: make the deployed chat (chat.vaticinus.com) a real tool-using agent that can use the data,
people, and capture tools, quality-first, on cheap DeepSeek orchestration.

## Architecture (reuses what exists)
- **Agent loop** already lives in `vati-data-agent/serve_http.py` (`/ask`, `/ask_stream`) driving
  `agent.py`'s DeepSeek function-calling loop over `TOOL_SPECS` (now incl. `people_search`,
  `capture_play`, `capture_targets`). NDJSON streaming is built to survive Cloudflare 524 on long runs.
- **Transport** already exists: the `data.vaticinus.com` EC2 tunnel that the chat's `/pack` sidecar
  uses. Same path, new endpoint.
- **Chat** = the Cloudflare Worker in `chat/` (Quick / Council / Deep modes).

## Steps
1. **EC2:** run `serve_http.py` under systemd (provisioning in `vati-data-agent/deploy/`), bound
   behind the `data.vaticinus.com` tunnel, with `VATI_API_TOKEN` set (bearer).
2. **Chat:** add an "Agent" mode (or fold into Deep) that POSTs the user turn to `/ask_stream` with
   the bearer, and renders the streamed steps + final note. ~1 fetch wrapper in `chat/src/lib`.
3. **Test** via the worker against the tunnel, then `pnpm ship`.

## Guardrails (non-negotiable, baked in before ship)
- **No send, anywhere users can reach.** The agent toolset has NO email-send tool and NO inbox tool.
  Capture tools are DRAFT-ONLY (they return text). The owner-only JMAP reader (`engine/capture/inbox.py`)
  is NOT in `TOOL_SPECS`/`server.py` and stays off the deployed surface — those are Toni's private inboxes.
- **Trust primer active** (catalog.py PRIMER) so the agent never fabricates and grounds on the real
  scored record.
- **Cost:** one `/ask` run = cents of DeepSeek (loop capped at ~18 steps). Owner unlimited; rate-limit
  anon/free users. `capture_targets` is the slow one (keyless Exa + DeepSeek) — gate it behind Deep tier.
- **Outward-facing:** do not ship without Toni's explicit go.
