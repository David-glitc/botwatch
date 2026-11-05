import httpx
import pytest

from botwatch.botscan import BotScan
from botwatch.store import Store

A = "0x" + "ab" * 20
B = "0x" + "cd" * 20


def tx(h, frm=B, to=A, value="2500000000000000000", method="transfer", result="success"):
    return {"hash": h, "from": {"hash": frm}, "to": {"hash": to}, "value": value, "method": method, "result": result, "raw_input": "0x"}


class FakeScan:
    """httpx.MockTransport-backed BOTScan: pages[path] -> JSON; counts hits per path."""

    def __init__(self):
        self.pages: dict[str, dict] = {}
        self.hits: dict[str, int] = {}

        def handler(req: httpx.Request):
            p = req.url.path.removeprefix("/api/v2")
            self.hits[p] = self.hits.get(p, 0) + 1
            if p in self.pages:
                return httpx.Response(200, json=self.pages[p])
            return httpx.Response(404, json={"message": "Not found"})

        self.scan = BotScan(httpx.AsyncClient(transport=httpx.MockTransport(handler)), base="https://x/api/v2", min_interval=0, ttl=0)


@pytest.fixture
def fake():
    return FakeScan()


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def sent():
    out: list[tuple[int, str]] = []

    async def send(chat, text):
        out.append((chat, text))

    send.out = out
    return send
