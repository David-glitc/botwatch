from html import escape

EXPLORER = "https://scan.botchain.ai"


def short(addr: str) -> str:
    return addr[:6] + "…" + addr[-4:] if len(addr) > 12 else addr


def bot_amount(wei: str | int | None) -> str:
    n = int(wei or 0)
    whole, frac = divmod(n, 10**18)
    f = f"{frac:018d}"[:4].rstrip("0")
    return f"{whole:,}" + (f".{f}" if f else "")


def _hash(party) -> str:
    return (party or {}).get("hash", "") if isinstance(party, dict) else ""


def format_tx(tx: dict, address: str, label: str = "") -> str:
    me = address.lower()
    frm, to = _hash(tx.get("from")), _hash(tx.get("to"))
    direction = "⬅️ in" if to.lower() == me else "➡️ out" if frm.lower() == me else "•"
    ok = "✅" if (tx.get("result") or tx.get("status")) in ("success", "ok") else "❌"
    method = tx.get("method") or ("transfer" if not tx.get("raw_input") or tx.get("raw_input") == "0x" else "call")
    name = escape(label) if label else f"<code>{short(address)}</code>"
    other = to if frm.lower() == me else frm
    url = f"{EXPLORER}/tx/{tx['hash']}"
    return (f"{ok} {direction} <b>{name}</b>: {escape(str(method))} · {bot_amount(tx.get('value'))} BOT"
            f" · {'with ' + '<code>' + short(other) + '</code>' if other else 'contract creation'}\n"
            f"<a href=\"{url}\">{short(tx['hash'])}</a>")


def format_price_alert(symbol: str, direction: str, threshold: float, price: float) -> str:
    arrow = "📈 above" if direction == "above" else "📉 below"
    return f"{arrow} <b>{escape(symbol)}</b> ${price:,.4f} crossed your ${threshold:,.4f} alert (one-shot, now off)."
