import asyncio
import time

import httpx
import pytest

from botwatch import commands, monitor
from botwatch.botscan import WBOT, BotScan
from botwatch.bot import build_router
from botwatch.formatting import bot_amount, format_tx, short
from botwatch.store import ADDR
from tests.conftest import A, B, tx


# ---- formatting
def test_bot_amount():
    assert bot_amount("2500000000000000000") == "2.5"
    assert bot_amount(0) == "0" and bot_amount(None) == "0"
    assert bot_amount(10**18 * 1234) == "1,234"
    assert bot_amount(1) == "0"  # dust below 4 decimals shows as 0


def test_format_tx_direction_and_escaping():
    inc = format_tx(tx("0x" + "11" * 32), A, "<b>vault</b>")
    assert "in" in inc and "&lt;b&gt;vault&lt;/b&gt;" in inc and "2.5 BOT" in inc and "scan.botchain.ai/tx/0x1111" in inc
    out = format_tx(tx("0x" + "22" * 32, frm=A, to=B), A)
    assert "out" in out and short(A) in out
    failed = format_tx(tx("0x" + "33" * 32, result="error"), A)
    assert "❌" in failed
    create = format_tx({"hash": "0x" + "44" * 32, "from": {"hash": A}, "to": None, "value": "0"}, A)
    assert "contract creation" in create


# ---- client
async def test_client_caches_and_rate_limits():
    hits = []

    def h(req):
        hits.append(time.monotonic())
        return httpx.Response(200, json={"items": []})

    s = BotScan(httpx.AsyncClient(transport=httpx.MockTransport(h)), base="https://x", min_interval=0.15, ttl=60)
    await s.get("/a"); await s.get("/a"); await s.get("/b")
    assert len(hits) == 2 and hits[1] - hits[0] >= 0.14
    with pytest.raises(httpx.HTTPStatusError):
        s2 = BotScan(httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))), base="https://x", min_interval=0)
        await s2.get("/boom")


async def test_token_price(fake):
    fake.pages[f"/tokens/{WBOT}"] = {"symbol": "WBOT", "exchange_rate": "12.5"}
    fake.pages["/tokens/0xnone"] = {"symbol": "NOP", "exchange_rate": None}
    assert await fake.scan.token_price(WBOT) == ("WBOT", 12.5)
    assert await fake.scan.token_price("0xnone") == ("NOP", None)


# ---- store
def test_store_watches_and_alerts(store):
    assert store.add_watch(1, A.upper().replace("0X", "0x")) and not store.add_watch(1, A)
    store.add_watch(2, A, "mine")
    assert {c for c, _ in store.chats_for(A)} == {1, 2}
    assert store.remove_watch(1, A) and not store.remove_watch(1, A)
    aid = store.add_alert(1, WBOT, "WBOT", "above", 15)
    assert store.alerts(1)[0][0] == aid
    assert not store.deactivate_alert(aid, chat_id=99)  # someone else's alert
    assert store.deactivate_alert(aid, chat_id=1) and store.alerts(1) == []


# ---- monitor
async def test_first_sight_primes_then_alerts_only_new(fake, store, sent):
    store.add_watch(7, A, "vault")
    fake.pages[f"/addresses/{A}/transactions"] = {"items": [tx("0x01"), tx("0x00")]}
    assert await monitor.check_watches(fake.scan, store, sent) == 0 and sent.out == []  # history is not replayed
    fake.pages[f"/addresses/{A}/transactions"] = {"items": [tx("0x02"), tx("0x01"), tx("0x00")]}
    assert await monitor.check_watches(fake.scan, store, sent) == 1
    assert sent.out[0][0] == 7 and "vault" in sent.out[0][1]
    assert await monitor.check_watches(fake.scan, store, sent) == 0  # nothing new: no duplicate
    assert len(sent.out) == 1


async def test_fan_out_cap_and_order(fake, store, sent):
    store.add_watch(1, A); store.add_watch(2, A)
    fake.pages[f"/addresses/{A}/transactions"] = {"items": [tx("0x00")]}
    await monitor.check_watches(fake.scan, store, sent)
    fake.pages[f"/addresses/{A}/transactions"] = {"items": [tx(f"0x{i:02x}") for i in range(9, -1, -1)]}  # 9 new, newest first
    await monitor.check_watches(fake.scan, store, sent)
    chat1 = [t for c, t in sent.out if c == 1]
    assert len(chat1) == 6 and "4 more" in chat1[-1]  # 5 shown + summary
    assert "0x0100"[:3] and "scan.botchain.ai/tx/0x01" in chat1[0]  # oldest new tx first
    assert [c for c, _ in sent.out].count(2) == 6  # the second watcher gets the same


async def test_failing_address_does_not_stop_cycle(fake, store, sent):
    store.add_watch(1, B); store.add_watch(1, A)
    fake.pages[f"/addresses/{A}/transactions"] = {"items": [tx("0x00")]}  # B is a 404
    await monitor.check_watches(fake.scan, store, sent)
    assert store.is_primed(A) and not store.is_primed(B)


async def test_price_alerts_fire_once(fake, store, sent):
    fake.pages[f"/tokens/{WBOT}"] = {"symbol": "WBOT", "exchange_rate": "12.5"}
    store.add_alert(1, WBOT, "WBOT", "above", 12.0)
    store.add_alert(2, WBOT, "WBOT", "below", 12.0)  # not crossed
    store.add_alert(3, WBOT, "WBOT", "above", 20.0)  # not crossed
    assert await monitor.check_alerts(fake.scan, store, sent) == 1
    assert sent.out[0][0] == 1 and "12.5000" in sent.out[0][1]
    assert await monitor.check_alerts(fake.scan, store, sent) == 0  # one-shot
    fake.pages[f"/tokens/{WBOT}"] = {"symbol": "WBOT", "exchange_rate": None}
    assert await monitor.check_alerts(fake.scan, store, sent) == 0  # no rate: stay armed
    assert len(store.alerts()) == 2


# ---- commands
async def run(cmd, args, fake, store, chat=1):
    return await commands.handle(cmd, args, chat, store, fake.scan)


async def test_commands(fake, store):
    assert "botwatch" in await run("/start", [], fake, store)
    assert "Usage" in await run("watch", ["nope"], fake, store)
    fake.pages[f"/addresses/{A}/transactions"] = {"items": [tx("0x00")]}
    r = await run("/watch@botwatch_bot", [A, "My", "vault"], fake, store)
    assert "Watching" in r and "My vault" in r
    assert store.is_primed(A)  # primed at /watch so the existing history never alerts
    assert "Already" in await run("watch", [A], fake, store)
    fake.pages[f"/tokens/{WBOT}"] = {"symbol": "WBOT", "exchange_rate": "12.4681"}
    assert "$12.4681" in await run("price", [], fake, store)
    assert "Alert #1" in await run("alert", ["bot", "above", "15"], fake, store)
    assert "Usage" in await run("alert", ["bot", "sideways", "15"], fake, store)
    assert "Usage" in await run("alert", ["bot", "above", "-3"], fake, store)
    listing = await run("list", [], fake, store)
    assert "My vault" in listing and "#1" in listing
    assert "No such" in await run("unalert", ["1"], fake, store, chat=2)  # cannot cancel another chat's alert
    assert "Removed" in await run("unalert", ["1"], fake, store)
    assert "Removed" in await run("unwatch", [A], fake, store)
    assert "Unknown" in await run("frobnicate", [], fake, store)


async def test_limits_and_unpriced_token(fake, store):
    for i in range(commands.MAX_WATCHES):
        store.add_watch(1, "0x" + f"{i:040x}")
    assert "Limit" in await run("watch", [B], fake, store)
    fake.pages["/tokens/0x" + "9" * 40] = {"symbol": "X", "exchange_rate": None}
    assert "no price" in await run("alert", ["0x" + "9" * 40, "above", "1"], fake, store)
    assert "didn't answer" in await run("price", ["0x" + "8" * 40], fake, store)  # 404 from BOTScan


def test_router_registers_commands(fake, store):
    r = build_router(store, fake.scan)
    assert len(r.message.handlers) == 1
    assert ADDR.match(A)


async def test_client_retries_once_on_timeout():
    calls = []

    def h(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(200, json={"ok": 1})

    s = BotScan(httpx.AsyncClient(transport=httpx.MockTransport(h)), base="https://x", min_interval=0)
    assert await s.get("/p") == {"ok": 1} and len(calls) == 2
