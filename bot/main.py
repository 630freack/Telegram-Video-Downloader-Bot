import logging
import os
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import BOT_TOKEN, ADMIN_ID, STORAGE_PATH, LOG_LEVEL, DATABASE_PATH
from utils.database import init_db, save_download, get_history
from utils.downloader import download_video
from utils.filesystem import list_folders, create_folder, rename_file, get_available_folders
from utils.userbot_sender import send_file_via_userbot

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL),
)
logger = logging.getLogger(__name__)

# States for conversation
CHOOSING_FOLDER, ENTERING_FILENAME = range(2)

def check_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    if not check_admin(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    
    welcome_message = (
        "Привет, администратор!\n"
        "Я бот для загрузки видео по ссылкам.\n\n"
        "Доступные команды:\n"
        "- /download <ссылка> — загрузить видео\n"
        "- /folders — показать папки\n"
        "- /create_folder <название> — создать папку\n"
        "- /rename <старое_имя> to <новое_имя> — переименовать файл\n"
        "- /history — история загрузок\n"
        "- /send <имя_файла> to <получатель> — отправить файл через аккаунт\n"
    )
    await update.message.reply_text(welcome_message)

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the download process."""
    user = update.effective_user
    if not check_admin(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return ConversationHandler.END

    if len(context.args) == 0:
        await update.message.reply_text("Укажите ссылку: /download <ссылка>")
        return ConversationHandler.END

    url = context.args[0]
    context.user_data['download_url'] = url

    # Check if link is valid
    # This will be implemented in downloader.py
    await update.message.reply_text(f"Проверяю ссылку: {url}")

    # Show available folders
    folders = get_available_folders(STORAGE_PATH)
    keyboard = [
        [InlineKeyboardButton(folder, callback_data=folder)] for folder in folders
    ]
    keyboard.append([InlineKeyboardButton("Создать новую папку", callback_data="create_new")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Выберите папку для сохранения:", reply_markup=reply_markup)
    return CHOOSING_FOLDER

async def folder_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle folder choice."""
    query = update.callback_query
    await query.answer()

    folder = query.data
    if folder == "create_new":
        await query.edit_message_text("Введите название новой папки:")
        context.user_data['creating_folder'] = True
        return CHOOSING_FOLDER
    
    context.user_data['selected_folder'] = folder
    await query.edit_message_text(f"Выбрана папка: {folder}\nВведите имя файла (или отправьте /skip для использования оригинального имени):")
    return ENTERING_FILENAME

async def handle_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle folder name input."""
    folder_name = update.message.text
    full_path = os.path.join(STORAGE_PATH, folder_name)
    
    try:
        create_folder(full_path)
        await update.message.reply_text(f"Папка '{folder_name}' создана.")
        context.user_data['selected_folder'] = folder_name
    except Exception as e:
        await update.message.reply_text(f"Ошибка при создании папки: {str(e)}")
        return ConversationHandler.END
    
    await update.message.reply_text(f"Выбрана папка: {folder_name}\nВведите имя файла (или отправьте /skip для использования оригинального имени):")
    return ENTERING_FILENAME

async def file_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle file name input."""
    file_name = update.message.text
    if file_name == "/skip":
        file_name = None
    
    context.user_data['file_name'] = file_name
    
    # Start download
    url = context.user_data['download_url']
    folder = context.user_data['selected_folder']
    folder_path = os.path.join(STORAGE_PATH, folder)
    
    await update.message.reply_text(f"Начинаю загрузку...")
    
    try:
        final_name = await download_video(url, folder_path, file_name, context, update.message.chat_id)
        file_path = os.path.join(folder_path, final_name)
        
        # Save to history
        save_download(url, final_name, file_path, datetime.now(), DATABASE_PATH)
        
        await update.message.reply_text(f"✅ Загрузка завершена: {final_name}")
        
        # Ask about sending via userbot
        keyboard = [
            [InlineKeyboardButton("Да", callback_data=f"send_yes_{final_name}"),
             InlineKeyboardButton("Нет", callback_data="send_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Отправить файл '{final_name}' через ваш аккаунт?", reply_markup=reply_markup)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка загрузки: {str(e)}")
    
    return ConversationHandler.END

async def send_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle send choice after download."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("send_yes"):
        file_name = data.split("_", 2)[2]
        await query.edit_message_text(f"Введите получателя для отправки '{file_name}':")
        context.user_data['waiting_for_recipient'] = True
        context.user_data['file_to_send'] = file_name
    else:
        await query.edit_message_text("Отправка отменена.")
    
async def handle_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle recipient input for userbot send."""
    if not context.user_data.get('waiting_for_recipient'):
        return
    
    recipient = update.message.text
    file_name = context.user_data['file_to_send']
    folder = context.user_data['selected_folder']
    file_path = os.path.join(STORAGE_PATH, folder, file_name)
    
    await update.message.reply_text(f"Отправляю '{file_name}' в '{recipient}' через ваш аккаунт...")
    
    try:
        await send_file_via_userbot(file_path, recipient)
        await update.message.reply_text("✅ Файл успешно отправлен через ваш аккаунт!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {str(e)}")
    
    context.user_data['waiting_for_recipient'] = False

async def folders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available folders."""
    user = update.effective_user
    if not check_admin(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    
    folders = list_folders(STORAGE_PATH)
    if folders:
        message = "Доступные папки:\n" + "\n".join([f"📁 {f}" for f in folders])
    else:
        message = "Нет доступных папок."
    await update.message.reply_text(message)

async def create_folder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new folder."""
    user = update.effective_user
    if not check_admin(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    
    if len(context.args) == 0:
        await update.message.reply_text("Укажите название папки: /create_folder <название>")
        return
    
    folder_name = " ".join(context.args)
    full_path = os.path.join(STORAGE_PATH, folder_name)
    
    try:
        create_folder(full_path)
        await update.message.reply_text(f"✅ Папка '{folder_name}' создана.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при создании папки: {str(e)}")

async def rename_file_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rename a file."""
    user = update.effective_user
    if not check_admin(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    
    text = " ".join(context.args)
    if " to " not in text:
        await update.message.reply_text("Использование: /rename <старое_имя> to <новое_имя>")
        return
    
    old_name, new_name = text.split(" to ", 1)
    old_path = os.path.join(STORAGE_PATH, old_name)
    new_path = os.path.join(STORAGE_PATH, new_name)
    
    try:
        rename_file(old_path, new_path)
        await update.message.reply_text(f"✅ Файл переименован: {old_name} → {new_name}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка переименования: {str(e)}")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show download history."""
    user = update.effective_user
    if not check_admin(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    
    records = get_history()
    if records:
        message = "История загрузок:\n"
        for rec in records:
            message += f"\n🔗 {rec[0]}\n📝 {rec[1]}\n📁 {rec[2]}\n📅 {rec[3]}\n"
    else:
        message = "История пуста."
    await update.message.reply_text(message)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    user = update.effective_user
    if not check_admin(user.id):
        await update.message.reply_text("Доступ запрещён.")
        return
    await update.message.reply_text("Неизвестная команда. Используйте /start для списка команд.")


def main() -> None:
    """Start the bot."""
    # Initialize database
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    init_db(DATABASE_PATH)
    
    # Create the Application and pass it your bot's token
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("folders", folders))
    application.add_handler(CommandHandler("create_folder", create_folder_cmd))
    application.add_handler(CommandHandler("rename", rename_file_cmd))
    application.add_handler(CommandHandler("history", history))
    
    # Download conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("download", download)],
        states={
            CHOOSING_FOLDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_folder_name),
                CallbackQueryHandler(folder_choice)
            ],
            ENTERING_FILENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, file_name_input)]
        },
        fallbacks=[CommandHandler("cancel", start)]
    )
    application.add_handler(conv_handler)
    
    # Handler for send choice callback
    application.add_handler(CallbackQueryHandler(send_choice, pattern="^send_"))
    
    # Handler for recipient input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_recipient))
    
    # Handle unknown commands (for non-admins too)
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Run the bot until the user presses Ctrl-C
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True))
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            pass
        else:
            raise

if __name__ == "__main__":
    main()
