"""
==============================================
  СКРИПТ АВТОРИЗАЦИИ — ЗАПУСТИ ОДИН РАЗ!
==============================================
Этот скрипт создаёт файл сессии для Pyrogram.
После успешной авторизации файл 'user_session.session'
будет сохранён, и бот сможет работать без повторной
авторизации.

Запуск:
    python create_session.py

Тебе нужно будет:
1. Ввести номер телефона (в формате +7XXXXXXXXXX)
2. Ввести код подтверждения из Telegram
3. Если есть 2FA пароль — ввести его
"""

import sys
import os
import asyncio

print("DEBUG: Global init started...", flush=True)
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Добавляем текущую директорию
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("DEBUG: Importing Pyrogram...", flush=True)
from pyrogram import Client
print("DEBUG: Pyrogram imported.", flush=True)

print("DEBUG: Importing config...", flush=True)
from config import API_ID, API_HASH, PROXY
print("DEBUG: Config imported.", flush=True)


def main():
    print("DEBUG: main() started", flush=True)
    print("==================================================")
    print("   TELEGRAM AUTHENTICATION (ASCII VERSION)")
    print("==================================================")
    print("This script will help you authorize your account.")
    print("You will need to enter your phone number (+7...)")
    print("and the code sent to your Telegram app.")
    print("==================================================")

    # Создаём клиент
    print("DEBUG: Initializing Pyrogram Client...", flush=True)
    app = Client(
        name="user_session",
        api_id=API_ID,
        api_hash=API_HASH,
        workdir=os.path.dirname(os.path.abspath(__file__)),
        proxy=PROXY
    )

    print("DEBUG: Attempting to connect to Telegram servers...", flush=True)
    try:
        app.connect()
        print("DEBUG: Connected! Now checking authorization state...", flush=True)
        
        if not app.get_me():
            print("DEBUG: Not authorized. Starting interactive login...", flush=True)
            # Если не авторизован, запускаем процесс входа
            # Note: app.start() handles everything interactively if needed
            app.disconnect() 
            print("DEBUG: Re-starting in interactive mode...", flush=True)
            with app:
                me = app.get_me()
                print("\nSUCCESS! Authorized as:", me.first_name)
                print(f"Session saved to user_session.session")
        else:
            me = app.get_me()
            print(f"\nALREADY AUTHORIZED as: {me.first_name}")
            print(f"Session file is healthy.")
            
    except Exception as e:
        print(f"\nERROR: Connection failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        try:
            app.disconnect()
        except:
            pass


if __name__ == "__main__":
    main()
