from telethon import TelegramClient
import os

# Import config
from config.config import API_ID, API_HASH

# Path to the session file
SESSION_PATH = 'bot_user_session'

async def send_file_via_userbot(file_path: str, recipient: str):
    """Send file via Telegram UserBot."""
    if not os.path.exists(file_path):
        raise Exception(f"Файл не найден: {file_path}")
    
    # Create client
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    try:
        await client.start()
        
        # Send file
        await client.send_file(
            recipient,
            file_path,
            caption=f"Файл отправлен через бота ({os.path.basename(file_path)})"
        )
        
    finally:
        await client.disconnect()