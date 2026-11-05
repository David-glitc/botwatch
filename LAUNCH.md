# Launch notes (needs your approval; nothing registered or deployed)

1. **Register the bot** with @BotFather (you, once, free) → `BOT_TOKEN`. Not done: no token exists.
2. **Hosting**: one always-on Python process (long polling, so no inbound port/webhook) with a small SQLite file.

| Option | Cost |
|---|---|
| Fly.io shared-1x 256 MB + 1 GB volume | ~$2–3/mo |
| $4–5 VPS (systemd unit) | ~$4–6/mo |
| This machine under systemd | $0, only while it is up |

Cloudflare Workers can't run it as is (needs a persistent poller); a webhook + cron Workers port with D1 would be free-tier but is a rewrite.
Load: ~1 BOTScan request per watched address per minute. Above ~40 distinct watched addresses, raise `POLL_SECS` or ask BOTScan about a key/higher limit.
Before public: add `/start` terms/privacy line (stores chat id + watched addresses only) and decide whether to cap users.
