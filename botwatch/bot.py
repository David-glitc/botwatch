import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message

from . import commands, monitor
from .botscan import BotScan
from .store import Store

COMMANDS = ["start", "help", "watch", "unwatch", "list", "price", "alert", "unalert"]


def build_router(store: Store, scan: BotScan) -> Router:
    r = Router()

    @r.message(Command(*COMMANDS))
    async def _(m: Message):
        parts = (m.text or "").split()
        reply = await commands.handle(parts[0], parts[1:], m.chat.id, store, scan)
        await m.answer(reply, disable_web_page_preview=True)

    return r


async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN (from @BotFather). To try the watcher without Telegram: python -m botwatch.dryrun 0x…")
    logging.basicConfig(level=logging.INFO)
    store, scan = Store(os.environ.get("BOTWATCH_DB", "botwatch.db")), BotScan()
    bot = Bot(token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(build_router(store, scan))

    async def send(chat_id: int, text: str):
        await bot.send_message(chat_id, text, disable_web_page_preview=True)

    task = asyncio.create_task(monitor.run(scan, store, send, float(os.environ.get("POLL_SECS", "60"))))
    try:
        await dp.start_polling(bot)
    finally:
        task.cancel()
        await scan.aclose()


if __name__ == "__main__":
    asyncio.run(main())
