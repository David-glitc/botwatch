# botwatch

A Telegram bot for BOT Chain. BOTScan has no notifications: you have to refresh an address page to see if anything happened.
botwatch pushes it to you.

- `/watch 0x… [label]` — a message for every new transaction on a wallet or contract (in/out, method, amount, tx link)
- `/alert bot above 15` / `/alert 0xTOKEN below 0.02` — one-shot BDEX price alerts (price = BOTScan's rate for the token, `bot` = WBOT)
- `/price`, `/list`, `/unwatch`, `/unalert <id>`

Read-only public data (BOTScan API). No keys, no wallet connection, no transactions.

## Run
```bash
uv venv .venv && uv pip install --python .venv/bin/python -e '.[test]'
# try it without Telegram: prints the messages a chat would get, live from BOTScan
.venv/bin/python -u -m botwatch.dryrun 0x37b746fa129d6bec0a2c0850c30ed272cecf0c10 --recent 3
# real bot: create a bot with @BotFather, then
BOT_TOKEN=123:abc .venv/bin/python -m botwatch.bot
```
Env: `BOT_TOKEN`, `BOTWATCH_DB` (default `botwatch.db`), `POLL_SECS` (60).

## Behaviour
- First sight of an address records its history silently; only later transactions alert. One fetch per address serves every chat watching it.
- At most 5 alerts per address per cycle, then "…and N more".
- Politeness: one BOTScan request per ≥1.1 s globally, 20 s response cache, one retry on timeout. 20 watches and 20 alerts per chat.
- Price alerts fire once and switch off; tokens without a BOTScan rate are refused.

## Tests
`.venv/bin/python -m pytest -q` — 13 tests, all against a mocked BOTScan (httpx MockTransport); no network, no bot token.
