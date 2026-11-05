"""Polite BOTScan client: >= min_interval between requests, responses cached for ttl seconds."""
import asyncio
import time

import httpx

BASE = "https://scan.botchain.ai/api/v2"
WBOT = "0xd5452816194a3784dba983426cce7c122f4abd30"  # BDEX wrapped BOT, priced by BOTScan


class BotScan:
    def __init__(self, client: httpx.AsyncClient | None = None, base: str = BASE,
                 min_interval: float = 1.1, ttl: float = 20.0):
        self.client = client or httpx.AsyncClient(timeout=20, headers={"User-Agent": "botwatch/0.1 (read-only)"})
        self.base, self.min_interval, self.ttl = base.rstrip("/"), min_interval, ttl
        self._lock = asyncio.Lock()
        self._last = 0.0
        self._cache: dict[str, tuple[float, dict]] = {}
        self.requests = 0

    async def get(self, path: str) -> dict:
        hit = self._cache.get(path)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        async with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                r = await self.client.get(self.base + path)
            except httpx.TransportError:  # BOTScan times out on very busy addresses now and then: one retry
                await asyncio.sleep(self.min_interval)
                self.requests += 1
                r = await self.client.get(self.base + path)
            r.raise_for_status()
            data = r.json()
        self._cache[path] = (time.monotonic(), data)
        return data

    async def address_txs(self, address: str) -> list[dict]:
        return (await self.get(f"/addresses/{address}/transactions")).get("items", [])

    async def token_price(self, address: str) -> tuple[str, float | None]:
        """(symbol, USD price or None if BOTScan has no rate)."""
        t = await self.get(f"/tokens/{address}")
        rate = t.get("exchange_rate")
        return (t.get("symbol") or address[:8], float(rate) if rate else None)

    async def aclose(self):
        await self.client.aclose()
