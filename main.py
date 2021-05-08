import asyncio
import os
import logging
import dotenv

from app.bot import DreamBot
from app.redis import Redis
from app.data.db import Db

dotenv.load_dotenv()
logging.basicConfig(level=logging.DEBUG)


async def main():
    api_key = os.environ.get('API_KEY')
    redis_url = os.environ.get('REDIS_URL')
    redis = Redis(redis_url, key_prefix='dream_bot')
    bot = DreamBot(token=api_key, redis=redis)
    await bot.start()


if __name__ == '__main__':
    asyncio.run(main())