import asyncio
import os
import logging
import dotenv

from app.bot import DreamBot


dotenv.load_dotenv()
logging.basicConfig(level=logging.DEBUG)


async def main():
    api_key = os.environ.get('API_KEY')
    bot = DreamBot(api_key)
    await bot.start()


if __name__ == '__main__':
    asyncio.run(main())
