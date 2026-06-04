from __future__ import annotations

import asyncio

from .bot import build_application


async def smoke_test() -> None:
    application = build_application()
    await application.initialize()
    try:
        me = await application.bot.get_me()
        print(f"telegram getMe ok: @{me.username}")
    finally:
        await application.shutdown()


def main() -> None:
    asyncio.run(smoke_test())


if __name__ == "__main__":
    main()
