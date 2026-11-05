"""Transport-free command logic: text in, HTML text out. aiogram handlers are thin wrappers (bot.py)."""
from html import escape

from .botscan import WBOT, BotScan
from .formatting import short
from .store import ADDR, Store

ALIASES = {"bot": WBOT, "wbot": WBOT}
HELP = (
    "<b>botwatch</b>: BOT Chain activity and BDEX price alerts (public data, no keys).\n\n"
    "/watch &lt;address&gt; [label]: alert me on new transactions\n"
    "/unwatch &lt;address&gt;\n/list: my watches and alerts\n"
    "/price [bot|token address]: current BDEX price\n"
    "/alert &lt;bot|token address&gt; above|below &lt;usd&gt;: one-shot price alert\n"
    "/unalert &lt;id&gt;"
)
MAX_WATCHES = 20
MAX_ALERTS = 20


async def handle(cmd: str, args: list[str], chat_id: int, store: Store, scan: BotScan) -> str:
    cmd = cmd.lower().lstrip("/").split("@")[0]
    if cmd in ("start", "help"):
        return HELP
    if cmd == "watch":
        if not args or not ADDR.match(args[0]):
            return "Usage: /watch 0x… [label]"
        if len(store.watches(chat_id)) >= MAX_WATCHES:
            return f"Limit of {MAX_WATCHES} watches reached."
        label = " ".join(args[1:])[:40]
        addr = args[0].lower()
        if not store.add_watch(chat_id, addr, label):
            return "Already watching that address."
        try:  # prime now so only transactions after this moment alert
            store.mark_seen(addr, [t["hash"] for t in await scan.address_txs(addr) if t.get("hash")])
        except Exception:
            pass  # the monitor primes on first sight instead
        return f"Watching <code>{short(addr)}</code>{' (' + escape(label) + ')' if label else ''}."
    if cmd == "unwatch":
        if not args or not ADDR.match(args[0]):
            return "Usage: /unwatch 0x…"
        return "Removed." if store.remove_watch(chat_id, args[0]) else "You weren't watching that."
    if cmd == "list":
        w, a = store.watches(chat_id), store.alerts(chat_id)
        if not w and not a:
            return "Nothing yet. Try /watch 0x… or /alert bot above 15"
        lines = [f"👁 <code>{short(x[1])}</code> {escape(x[2])}".rstrip() for x in w]
        lines += [f"🔔 #{i} {escape(s)} {d} ${t:,.4f}" for i, _, _, s, d, t in a]
        return "\n".join(lines)
    if cmd == "price":
        token = _token(args[0] if args else "bot")
        if not token:
            return "Usage: /price [bot|0x token address]"
        try:
            symbol, price = await scan.token_price(token)
        except Exception:
            return "BOTScan didn't answer. Try again shortly."
        return f"<b>{escape(symbol)}</b>: " + (f"${price:,.4f}" if price is not None else "no price on BOTScan yet")
    if cmd == "alert":
        if len(args) != 3 or args[1].lower() not in ("above", "below"):
            return "Usage: /alert bot above 15"
        token = _token(args[0])
        try:
            threshold = float(args[2].lstrip("$"))
        except ValueError:
            threshold = -1
        if not token or threshold <= 0:
            return "Usage: /alert bot above 15"
        if len(store.alerts(chat_id)) >= MAX_ALERTS:
            return f"Limit of {MAX_ALERTS} alerts reached."
        try:
            symbol, price = await scan.token_price(token)
        except Exception:
            return "BOTScan didn't answer. Try again shortly."
        if price is None:
            return "That token has no price on BOTScan, so I can't alert on it."
        aid = store.add_alert(chat_id, token, symbol, args[1].lower(), threshold)
        return f"Alert #{aid}: {escape(symbol)} {args[1].lower()} ${threshold:,.4f} (now ${price:,.4f})."
    if cmd == "unalert":
        if not args or not args[0].isdigit():
            return "Usage: /unalert <id>"
        return "Removed." if store.deactivate_alert(int(args[0]), chat_id) else "No such alert."
    return "Unknown command. /help"


def _token(arg: str) -> str | None:
    a = arg.lower()
    return ALIASES.get(a) or (a if ADDR.match(a) else None)
