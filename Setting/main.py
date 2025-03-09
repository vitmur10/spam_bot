import asyncio

from const import *
from filters import router, auto_unban_unmute


async def main():
    asyncio.create_task(auto_unban_unmute(bot))
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
