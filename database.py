import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data.db")
FREE_LIMIT = 3

def init_db():
    """Инициализирует базу данных."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                requests_made INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

def get_user_status(user_id: int):
    """Возвращает статус пользователя (количество сделанных запросов и премиум)."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT requests_made, is_premium FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            return {"requests_made": result[0], "is_premium": bool(result[1])}
        else:
            # Создаем нового пользователя
            cursor.execute("INSERT INTO users (user_id, requests_made) VALUES (?, ?)", (user_id, 0))
            conn.commit()
            return {"requests_made": 0, "is_premium": False}

def increment_request(user_id: int):
    """Увеличивает счетчик запросов пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET requests_made = requests_made + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

def check_access(user_id: int, admin_list: list) -> bool:
    """Проверяет, есть ли у пользователя доступ (админ, премиум или есть попытки)."""
    if user_id in admin_list:
        return True
    
    status = get_user_status(user_id)
    if status["is_premium"]:
        return True
    
    return status["requests_made"] < FREE_LIMIT

def get_remaining_attempts(user_id: int, admin_list: list):
    """Возвращает количество оставшихся бесплатных попыток."""
    if user_id in admin_list:
        return float('inf')
    
    status = get_user_status(user_id)
    if status["is_premium"]:
        return float('inf')
    
    remaining = FREE_LIMIT - status["requests_made"]
    return max(0, remaining)

# Инициализируем БД при импорте
init_db()
