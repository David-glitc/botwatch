"""Try botwatch against live BOTScan with no Telegram: prints the messages a chat would receive.

  python -m botwatch.dryrun 0xADDRESS [0xADDRESS...] [--recent N]
Shows the latest N transactions formatted as alerts (default 3), then polls every 30 s for new ones.
"""
import asyncio
import sys

from .botscan import WBOT, BotScan
from .formatting import format_tx
from .monitor import check_alerts, check_watches
from .store import ADDR, Store


async def main(argv: list[str]):
    recent = 3
    if "--recent" in argv:
        i = argv.index("--recent")
        recent = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    addrs = [a for a in argv if ADDR.match(a)]
    if not addrs:
        raise SystemExit(__doc__)
    scan, store = BotScan(), Store(":memory:")

    async def send(chat: int, text: str):
        print(f"\n[chat {chat}]\n{text}")

    sym, price = await scan.token_price(WBOT)
    print(f"{sym} price: {price}")
    for a in addrs:
        for tx in (await scan.address_txs(a))[:recent][::-1]:
            await send(0, format_tx(tx, a))
        store.add_watch(0, a)
    store.add_alert(0, WBOT, sym, "above", 1.0)  # fires immediately: demonstrates the alert format
    await check_alerts(scan, store, send)
    await check_watches(scan, store, send)  # primes
    print(f"\nwatching {len(addrs)} address(es); Ctrl-C to stop ({scan.requests} requests so far)")
    while True:
        await asyncio.sleep(30)
        await check_watches(scan, store, send)


if __name__ == "__main__":
    try:
        asyncio.run(main(sys.argv[1:]))
    except KeyboardInterrupt:
        pass
