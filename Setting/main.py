import asyncio

from const import *
from filters import router, auto_moderation_loop, auto_ban_users


async def main():
    asyncio.create_task(auto_moderation_loop(bot))
    asyncio.create_task(auto_ban_users())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
