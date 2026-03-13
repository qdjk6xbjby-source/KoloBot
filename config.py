import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# 1. Токен бота от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 2. API ID и API HASH с https://my.telegram.org
API_ID = os.getenv("API_ID")
if API_ID:
    API_ID = int(API_ID)
API_HASH = os.getenv("API_HASH")

# 3. Твой Telegram ID (узнать можно у @userinfobot)
#    Пользователи из этого списка всегда имеют полный доступ (админы)
raw_allowed = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [int(u.strip()) for u in raw_allowed.split(",") if u.strip().isdigit()]

# 4. Прокси (Необязательно). Если Telegram блокируется провайдером.
PROXY = None
