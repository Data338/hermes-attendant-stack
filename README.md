# hermes-attendant-stack

Production-tested stack for a WhatsApp service attendant on the Hermes agent gateway (bring your own `hermes-base` image): one container, one agent, zero stock messages reaching the customer.

```
WhatsApp ──▶ attendant (bot mode, allowlist) ──▶ LLM provider
                  │  chat-only: no shell, no files
                  │  PDF auto-extract (pdftotext → context)
                  └── templates/SOUL.md + AGENTS.md = persona + domain brain
```

Two transport modes:
- **Baileys bridge** (unofficial, QR pairing) — `WHATSAPP_ENABLED=true`.
- **Official WhatsApp Cloud API** (Graph + webhook) — see
  [`SKILL.md`](SKILL.md) for the full field guide (Meta hierarchy, the 3 webhook
  locks, Cloudflare named tunnel, and the silent-drop gotcha).

## What's inside

| File | What |
|---|---|
| `compose.yaml` | Single-service stack (host network for the WA bridge, persistent state volume) |
| `Dockerfile` | `hermes-base` + node/sqlite3/poppler-utils + gateway patches |
| `patches.py` | 4 patches against the gateway code, assert-anchored: onboarding intro fully off, PDF auto-extract into context, WhatsApp version fetch via `web.whatsapp.com` (no more GitHub 429s), all internal Hermes notices suppressed on WhatsApp **and** Cloud API |
| `SKILL.md` | Field guide: navigate the Meta + Cloudflare ecosystems without pain (webhook locks, named tunnel, silent-drop fix) |
| `templates/SOUL.md` | Attendant persona template (`{{PLACEHOLDERS}}` for name, business, branches) |
| `templates/AGENTS.md` | Domain knowledge-base template (collection order, branch flows, glossary) |
| `templates/config.yaml` | Least-privilege gateway config (chat-only toolsets, MCP backend hook, creds via env) |
| `provider.env.example` | Copy to `provider.env`. Never commit the real one |

## Quick start

```bash
cp provider.env.example provider.env   # fill in your provider key
cp templates/SOUL.md SOUL.md           # replace {{PLACEHOLDERS}}
cp templates/AGENTS.md AGENTS.md
cp templates/config.yaml config.yaml
docker compose up -d --build
# scan the QR in logs, add your number to the allowlist, done
```

The agent state (sessions, WhatsApp pairing, memory) lives in the `attendant-state` volume at `/opt/data`. The gateway reads `SOUL.md`, `AGENTS.md`, and `config.yaml` from that state dir — copy them there on first boot:

```bash
docker cp SOUL.md attendant:/opt/data/SOUL.md
docker cp AGENTS.md attendant:/opt/data/AGENTS.md
docker cp config.yaml attendant:/opt/data/config.yaml
docker restart attendant
```

## Remote control

Pair with [whatsapp-agent-control-plane](https://github.com/Data338/whatsapp-agent-control-plane): a second agent that supervises this one through the shared state volume (`.restart-flag` porter, cron delivery, read-only SQLite recipes).

## Privacy

Customer data (names, IDs, documents) lives ONLY in the state volume and the provider's API calls. Nothing here phones home. `provider.env`, `*.db`, `whatsapp/`, `sessions/`, and `*.png` (QR) are git-ignored — keep it that way.

## License

MIT — see [LICENSE](LICENSE).
