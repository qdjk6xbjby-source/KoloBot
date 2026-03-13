"""
==============================================
  TELEGRAM MEDIA GRABBER BOT
==============================================
Бот для скачивания медиа из закрытых Telegram-каналов.

Перед запуском:
1. Заполни config.py
2. Запусти create_session.py для авторизации
3. Запусти этот файл: python bot.py
"""

import os
import sys
import asyncio
import logging
import time

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Добавляем текущую директорию
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

from config import BOT_TOKEN, API_ID, API_HASH, ALLOWED_USERS, PROXY
from grabber import TelegramGrabber, parse_telegram_link
from database import check_access, increment_request, get_remaining_attempts

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("bot")

# ============================================
#  Инициализация
# ============================================

bot = Client(
    name="grabber_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=os.path.dirname(os.path.abspath(__file__)),
    max_concurrent_transmissions=1,
    proxy=PROXY
)

# Граббер (работает через User API)
grabber = TelegramGrabber()


# ============================================
#  Утилиты
# ============================================



def format_size(size_bytes: int) -> str:
    """Форматирует размер файла в читаемый вид."""
    if not size_bytes:
        return "неизвестно"
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} ГБ"


MEDIA_TYPE_NAMES = {
    "video": "🎬 Видео",
    "photo": "📸 Фото",
    "animation": "🎞 GIF",
    "document": "📄 Документ",
    "video_note": "⭕ Видеосообщение",
    "voice": "🎤 Голосовое",
    "audio": "🎵 Аудио",
    "sticker": "🃏 Стикер",
}


class ProgressCallback:
    """Класс для отслеживания прогресса (без вывода в чат)."""
    def __init__(self, message: Message, action_text: str):
        self.message = message
        self.action_text = action_text
        self.last_update_time = time.time()

    async def __call__(self, current, total, idx=None, total_items=None, filename=None, action="download"):
        # Мы больше не редактируем сообщение каждые 2 секунды, 
        # чтобы не создавать эффект "мигания" и не выглядеть устаревшим.
        pass


# ============================================
#  Команда /start
# ============================================

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    remaining = get_remaining_attempts(message.from_user.id, ALLOWED_USERS)
    
    status_text = ""
    if remaining == float('inf'):
        status_text = "🔓 **У вас неограниченный доступ (Admin/Premium).**"
    else:
        status_text = f"🎁 **У вас осталось бесплатных попыток: {remaining}**"

    await message.reply(
        f"👋 **Привет! Я Media Grabber Bot**\n\n"
        "Отправь мне ссылку на сообщение из Telegram-канала, "
        "и я скачаю оттуда видео или фото.\n\n"
        f"{status_text}\n\n"
        "**Поддерживаемые форматы ссылок:**\n"
        "• `https://t.me/c/123456/789` — приватный канал\n"
        "• `https://t.me/channel/789` — публичный канал\n\n"
        "**Поддерживаемые типы медиа:**\n"
        "🎬 Видео • 📸 Фото • 🎞 GIF • 📄 Документы",
        parse_mode=ParseMode.MARKDOWN
    )

@bot.on_message(filters.command("status") & filters.private)
async def status_command(client: Client, message: Message):
    remaining = get_remaining_attempts(message.from_user.id, ALLOWED_USERS)
    
    if remaining == float('inf'):
        await message.reply("🌟 У вас **премиум-доступ** или вы **администратор**. Ограничений нет!")
    elif remaining > 0:
        await message.reply(f"📊 У вас осталось **{remaining}** бесплатных скачиваний.")
    else:
        await message.reply("❌ Бесплатные попытки закончились. Для пополнения свяжитесь с администратором.")


# ============================================
#  Обработка ссылок
# ============================================

@bot.on_message(filters.text & filters.private)
async def handle_link(client: Client, message: Message):
    if not check_access(message.from_user.id, ALLOWED_USERS):
        await message.reply("❌ У вас закончились бесплатные попытки. Свяжитесь с админом для покупки доступа.")
        return

    text = message.text.strip()

    # Проверяем, что это ссылка на Telegram
    if not ("t.me/" in text):
        await message.reply(
            "🔗 Отправь мне ссылку на сообщение из Telegram-канала.\n"
            "Пример: `https://t.me/c/123456/789`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Проверяем, что ссылка парсится
    parsed = parse_telegram_link(text)
    if parsed is None:
        await message.reply(
            "❌ Не удалось распознать ссылку.\n\n"
            "**Поддерживаемые форматы:**\n"
            "• `https://t.me/c/CHANNEL_ID/MSG_ID`\n"
            "• `https://t.me/USERNAME/MSG_ID`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Отправляем статус
    status_msg = await message.reply("⏳ Начинаю скачивание...")
    progress = ProgressCallback(status_msg, "")

    # Скачиваем
    result = await grabber.download_media(text, progress_callback=progress)

    if not result["success"]:
        await status_msg.edit_text(result.get("error") or "❌ Неизвестная ошибка.")
        return

    items = result.get("items", [])
    if not items:
        await status_msg.edit_text("❌ Файлы не найдены.")
        return

    # === ОДИН ФАЙЛ ===
    if len(items) == 1:
        item = items[0]
        media_name = MEDIA_TYPE_NAMES.get(item["media_type"], "📎 Файл")
        
        # Убираем лишний текст, оставляем только статус отправки
        await status_msg.edit_text(f"🚀 Отправляю...")

        file_path = item["file_path"]

        # Функция прогресса для отправки (замыкание)
        async def upload_progress(current, total, *args):
            await progress(current, total, 1, 1, item["file_name"], "upload")

        try:
            # Отправляем в зависимости от типа. 
            # Для видео не добавляем лишних подписей с размером, чтобы выглядело как пост.
            if item["media_type"] == "photo":
                await client.send_photo(message.chat.id, photo=file_path, progress=upload_progress)
            elif item["media_type"] == "video":
                # supports_streaming=True помогает Telegram не перекодировать видео (если формат подходит)
                await client.send_video(
                    message.chat.id, 
                    video=file_path, 
                    supports_streaming=True, 
                    progress=upload_progress
                )
            elif item["media_type"] == "animation":
                await client.send_animation(message.chat.id, animation=file_path, progress=upload_progress)
            elif item["media_type"] == "voice":
                await client.send_voice(message.chat.id, voice=file_path, progress=upload_progress)
            elif item["media_type"] == "audio":
                await client.send_audio(message.chat.id, audio=file_path, progress=upload_progress)
            elif item["media_type"] == "video_note":
                await client.send_video_note(message.chat.id, video_note=file_path, progress=upload_progress)
            elif item["media_type"] == "sticker":
                await client.send_sticker(message.chat.id, sticker=file_path, progress=upload_progress)
            else:
                await client.send_document(message.chat.id, document=file_path, progress=upload_progress)

            # Удаляем статусное сообщение
            await status_msg.delete()
            # Списываем попытку после успешного скачивания
            increment_request(message.from_user.id)
            log.info(f"Отправлено: {item['media_type']} | {item['file_name']} | {size_str} | user={message.from_user.id}")

        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка при отправке: {str(e)}")
            log.error(f"Ошибка отправки: {e}")

        finally:
            # Удаляем временный файл
            grabber.cleanup(file_path)

    # === АЛЬБОМ (МЕДИАГРУППА) ===
    else:
        await status_msg.edit_text(f"📤 Отправляю альбом ({len(items)} файлов)...")
        from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio

        media_group = []
        for idx, item in enumerate(items):
            media_name = MEDIA_TYPE_NAMES.get(item["media_type"], "📎 Файл")
            size_str = format_size(item["file_size"])
            caption = f"Альбом • {len(items)} файлов\n{media_name} • {size_str}" if idx == 0 else ""
            
            # В Pyrogram для медиагрупп используются только эти 4 типа InputMedia
            if item["media_type"] == "photo":
                media_group.append(InputMediaPhoto(item["file_path"], caption=caption))
            elif item["media_type"] == "video":
                media_group.append(InputMediaVideo(item["file_path"], caption=caption))
            elif item["media_type"] == "audio":
                media_group.append(InputMediaAudio(item["file_path"], caption=caption))
            else:
                media_group.append(InputMediaDocument(item["file_path"], caption=caption))
                
        try:
            await client.send_media_group(message.chat.id, media=media_group)
            await status_msg.delete()
            # Списываем попытку после успешного скачивания (альбом)
            increment_request(message.from_user.id)
            log.info(f"Отправлен альбом ({len(items)} файлов) | user={message.from_user.id}")
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка при отправке альбома: {str(e)}")
            log.error(f"Ошибка отправки альбома: {e}")
        finally:
            # Удаляем все временные файлы
            for item in items:
                grabber.cleanup(item["file_path"])


# ============================================
#  Запуск
# ============================================

async def main():
    """Запуск бота и граббера."""
    log.info("Запуск граббера (User API)...")
    await grabber.start()
    log.info("Граббер запущен!")

    log.info("Запуск бота...")
    await bot.start()
    log.info("=" * 40)
    log.info("  БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
    log.info("=" * 40)

    # Ожидаем завершения
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        # Проверяем, что конфиг заполнен
        if BOT_TOKEN == "СЮДА_ВСТАВЬ_ТОКЕН_БОТА":
            print("❌ Заполни BOT_TOKEN в config.py!")
            sys.exit(1)
        if API_HASH == "СЮДА_ВСТАВЬ_API_HASH":
            print("❌ Заполни API_ID и API_HASH в config.py!")
            sys.exit(1)

        # Проверяем наличие сессии
        workdir = os.path.dirname(os.path.abspath(__file__))
        session_file = os.path.join(workdir, "user_session.session")
        if not os.path.exists(session_file):
            print("❌ Файл сессии не найден!")
            print("   Сначала запусти: python create_session.py")
            sys.exit(1)

        bot.run(main())

    except KeyboardInterrupt:
        log.info("Бот остановлен.")
    except Exception as e:
        log.error(f"Критическая ошибка: {e}")
        raise
