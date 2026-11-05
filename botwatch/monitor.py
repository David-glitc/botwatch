import asyncio
import logging
from typing import Awaitable, Callable

from .botscan import BotScan
from .formatting import format_price_alert, format_tx
from .store import Store

Send = Callable[[int, str], Awaitable[None]]
log = logging.getLogger("botwatch")
MAX_PER_CYCLE = 5  # per address; the rest are summarised, so a busy contract can't flood a chat


async def check_watches(scan: BotScan, store: Store, send: Send) -> int:
    sent = 0
    for addr in store.watched_addresses():
        try:
            txs = await scan.address_txs(addr)
        except Exception as e:  # one failing address must not stop the cycle
            log.warning("txs %s failed: %s", addr, e)
            continue
        hashes = [t["hash"] for t in txs if t.get("hash")]
        if not store.is_primed(addr):
            store.mark_seen(addr, hashes)  # first sight: remember history, don't replay it
            continue
        fresh = set(store.unseen(addr, hashes))
        if not fresh:
            continue
        new = [t for t in reversed(txs) if t.get("hash") in fresh]  # oldest first
        shown, extra = new[:MAX_PER_CYCLE], len(new) - MAX_PER_CYCLE
        for chat, label in store.chats_for(addr):
            for t in shown:
                await send(chat, format_tx(t, addr, label))
                sent += 1
            if extra > 0:
                await send(chat, f"…and {extra} more new transactions on <code>{addr[:10]}…</code>")
                sent += 1
        store.mark_seen(addr, list(fresh))
    return sent


async def check_alerts(scan: BotScan, store: Store, send: Send) -> int:
    fired = 0
    prices: dict[str, float | None] = {}
    for aid, chat, token, symbol, direction, threshold in store.alerts():
        if token not in prices:
            try:
                prices[token] = (await scan.token_price(token))[1]
            except Exception as e:
                log.warning("price %s failed: %s", token, e)
                prices[token] = None
        p = prices[token]
        if p is None:
            continue
        if (direction == "above" and p >= threshold) or (direction == "below" and p <= threshold):
            if store.deactivate_alert(aid):
                await send(chat, format_price_alert(symbol, direction, threshold, p))
                fired += 1
    return fired


async def run(scan: BotScan, store: Store, send: Send, interval: float = 60.0):
    while True:
        try:
            await check_watches(scan, store, send)
            await check_alerts(scan, store, send)
        except Exception:
            log.exception("monitor cycle failed")
        await asyncio.sleep(interval)
