from telegram.ext import Updater
from telegram import Bot
import asyncio

async def test():
    bot = Bot('test')
    updater = Updater(bot=bot, update_queue=asyncio.Queue())
    print('Updater created successfully')

asyncio.run(test())
