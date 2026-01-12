import os
import aiohttp
import asyncio
from urllib.parse import urlparse

async def check_url(session: aiohttp.ClientSession, url: str) -> bool:
    """Check if URL is accessible."""
    try:
        async with session.head(url, allow_redirects=True, timeout=10) as response:
            return response.status == 200 and 'text/html' not in response.headers.get('Content-Type', '')
    except Exception:
        return False

def get_filename_from_url(url: str) -> str:
    """Extract filename from URL."""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    if not filename:
        filename = "video.mp4"
    return filename

def get_unique_filename(directory: str, filename: str) -> str:
    """Generate unique filename if file already exists."""
    name, ext = os.path.splitext(filename)
    counter = 1
    unique_name = filename
    while os.path.exists(os.path.join(directory, unique_name)):
        unique_name = f"{name}_{counter}{ext}"
        counter += 1
    return unique_name

async def download_video(url: str, folder_path: str, file_name: str, context, chat_id: int) -> str:
    """Download video from URL with progress reporting."""
    async with aiohttp.ClientSession() as session:
        if not await check_url(session, url):
            raise Exception("Ссылка недоступна или не является файлом.")
        
        # Get filename
        if not file_name:
            file_name = get_filename_from_url(url)
        
        # Ensure unique filename
        final_name = get_unique_filename(folder_path, file_name)
        file_path = os.path.join(folder_path, final_name)
        
        # Send initial message
        message = await context.bot.send_message(chat_id=chat_id, text=f"📥 Начинаю загрузку: {final_name}")
        
        # Download with progress
        async with session.get(url) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB
            
            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if downloaded % (chunk_size * 5) == 0 or downloaded == total_size:  # Every 5MB or end
                            await context.bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=message.message_id,
                                text=f"📥 Загрузка: {final_name}\n{downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB ({percent:.1f}%)")

        # Final message
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message.message_id,
            text=f"✅ Загрузка завершена: {final_name}")
        
        return final_name
