"""
Модуль для скачивания медиа из Telegram каналов через Pyrogram.
Использует сессию пользователя для доступа к закрытым каналам.
"""

import os
import re
import tempfile
from pyrogram import Client
from pyrogram.errors import (
    ChannelPrivate,
    MessageIdInvalid,
    PeerIdInvalid,
    FloodWait
)
import asyncio
import time

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from config import API_ID, API_HASH, PROXY

# Директория для временных файлов
TEMP_DIR = os.path.join(tempfile.gettempdir(), "tg_grabber")
os.makedirs(TEMP_DIR, exist_ok=True)

# Паттерны для парсинга ссылок
# Приватный канал: https://t.me/c/1234567890/123
PRIVATE_LINK = re.compile(r"https?://t\.me/c/(\d+)/(\d+)")
# Публичный канал: https://t.me/channel_name/123
PUBLIC_LINK = re.compile(r"https?://t\.me/([a-zA-Z_][a-zA-Z0-9_]{3,})/(\d+)")


def parse_telegram_link(url: str):
    """
    Парсит ссылку на сообщение в Telegram.
    
    Возвращает (chat_id, message_id) или None.
    Для приватных каналов chat_id будет отрицательным числом.
    Для публичных — строкой (username).
    """
    url = url.strip()

    # Проверяем приватную ссылку
    match = PRIVATE_LINK.search(url)
    if match:
        channel_id = match.group(1)
        message_id = int(match.group(2))
        # Приватные каналы имеют ID вида -100XXXXXXXXXX
        chat_id = int(f"-100{channel_id}")
        return chat_id, message_id

    # Проверяем публичную ссылку
    match = PUBLIC_LINK.search(url)
    if match:
        username = match.group(1)
        message_id = int(match.group(2))
        return username, message_id

    return None


class TelegramGrabber:
    """Класс для скачивания медиа из Telegram."""

    def __init__(self):
        workdir = os.path.dirname(os.path.abspath(__file__))
        session_path = os.path.join(workdir, "user_session.session")
        
        if not os.path.exists(session_path):
            raise FileNotFoundError(
                "Файл сессии не найден! Сначала запусти: python create_session.py"
            )
        
        self.client = Client(
            name="user_session",
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=workdir,
            no_updates=True,  # Не получаем обновления — только запросы
            proxy=PROXY
        )
        self._started = False

    async def start(self):
        """Запускает клиент Pyrogram."""
        if not self._started:
            await self.client.start()
            self._started = True

    async def stop(self):
        """Останавливает клиент Pyrogram."""
        if self._started:
            await self.client.stop()
            self._started = False

    async def download_media(self, url: str, progress_callback=None) -> dict:
        """
        Скачивает медиа по ссылке на сообщение.
        Поддерживает медиагруппы (альбомы).
        
        Возвращает словарь:
        {
            "success": True/False,
            "error": "описание ошибки" или None,
            "items": [
                {
                    "file_path": "путь к файлу",
                    "media_type": "photo" / "video" / "document" / "animation" / ...,
                    "file_name": "имя файла",
                    "file_size": размер в байтах
                }, ...
            ]
        }
        """
        result: dict = {
            "success": False,
            "error": None,
            "items": []
        }

        # Парсим ссылку
        parsed = parse_telegram_link(url)
        if parsed is None:
            result["error"] = (
                "❌ Не удалось распознать ссылку.\n\n"
                "Поддерживаемые форматы:\n"
                "• https://t.me/c/CHANNEL_ID/MESSAGE_ID (приватный)\n"
                "• https://t.me/USERNAME/MESSAGE_ID (публичный)"
            )
            return result

        chat_id, message_id = parsed

        try:
            await self.start()

            # Получаем сообщение
            message = await self.client.get_messages(chat_id, message_id)

            if message.empty:
                result["error"] = "❌ Сообщение не найдено или было удалено."
                return result

            # Проверяем, часть ли это медиагруппы
            if message.media_group_id:
                messages = await self.client.get_media_group(chat_id, message_id)
            else:
                messages = [message]
            
            total_items = len(messages)

            for idx, msg in enumerate(messages, 1):
                item = {}
                
                # Определяем тип медиа
                if msg.video:
                    item["media_type"] = "video"
                    item["file_name"] = msg.video.file_name or f"video_{msg.id}.mp4"
                    item["file_size"] = msg.video.file_size
                elif msg.photo:
                    item["media_type"] = "photo"
                    item["file_name"] = f"photo_{msg.id}.jpg"
                    item["file_size"] = msg.photo.file_size
                elif msg.animation:
                    item["media_type"] = "animation"
                    item["file_name"] = msg.animation.file_name or f"animation_{msg.id}.mp4"
                    item["file_size"] = msg.animation.file_size
                elif msg.document:
                    item["media_type"] = "document"
                    item["file_name"] = msg.document.file_name or f"document_{msg.id}"
                    item["file_size"] = msg.document.file_size
                elif msg.video_note:
                    item["media_type"] = "video_note"
                    item["file_name"] = f"video_note_{msg.id}.mp4"
                    item["file_size"] = msg.video_note.file_size
                elif msg.voice:
                    item["media_type"] = "voice"
                    item["file_name"] = f"voice_{msg.id}.ogg"
                    item["file_size"] = msg.voice.file_size
                elif msg.audio:
                    item["media_type"] = "audio"
                    item["file_name"] = msg.audio.file_name or f"audio_{msg.id}.mp3"
                    item["file_size"] = msg.audio.file_size
                elif msg.sticker:
                    item["media_type"] = "sticker"
                    item["file_name"] = f"sticker_{msg.id}.webp"
                    item["file_size"] = msg.sticker.file_size
                else:
                    if total_items == 1:
                        result["error"] = "❌ В этом сообщении нет медиафайлов (видео, фото и т.д.)."
                        return result
                    continue

                # Функция прогресса для одного файла из группы
                async def progress(current, total, *args):
                    if progress_callback:
                        # args: (idx, total_items, filename, action)
                        await progress_callback(current, total, idx, total_items, item["file_name"], "download")

                # Скачиваем медиа
                file_path = await self.client.download_media(
                    msg,
                    file_name=os.path.join(TEMP_DIR, item["file_name"]),
                    progress=progress
                )

                if file_path:
                    item["file_path"] = file_path
                    result["items"].append(item)
                elif total_items == 1:
                    result["error"] = "❌ Не удалось скачать файл."
                    return result

            if result["items"]:
                result["success"] = True
            elif not result["error"]:
                result["error"] = "❌ Не удалось скачать медиафайлы."

        except ChannelPrivate:
            result["error"] = (
                "❌ Нет доступа к каналу.\n"
                "Убедись, что твой аккаунт подписан на этот канал."
            )
        except MessageIdInvalid:
            result["error"] = "❌ Неверный ID сообщения."
        except PeerIdInvalid:
            result["error"] = "❌ Неверный ID канала/чата."
        except FloodWait as e:
            result["error"] = f"⏳ Telegram ограничил запросы. Подожди {e.value} секунд."
        except Exception as e:
            result["error"] = f"❌ Ошибка: {type(e).__name__}: {str(e)}"

        return result

    def cleanup(self, file_path: str):
        """Удаляет временный файл после отправки."""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
