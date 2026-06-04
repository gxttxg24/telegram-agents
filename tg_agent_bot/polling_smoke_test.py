from __future__ import annotations

import asyncio

from telegram import Update

from .bot import build_application


async def polling_smoke_test(seconds: float = 5.0) -> None:
    application = build_application()
    await application.initialize()
    await application.start()
    try:
        if application.updater is None:
            raise RuntimeError("Application updater is not available.")

        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        print("telegram polling ok")
        await asyncio.sleep(seconds)
    finally:
        if application.updater is not None and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()


def main() -> None:
    asyncio.run(polling_smoke_test())


if __name__ == "__main__":
    main()
