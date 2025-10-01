# db.py

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import json
from datetime import date, datetime

load_dotenv()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                name TEXT,
                readings_balance INTEGER DEFAULT 1,
                total_used INTEGER DEFAULT 0,
                last_card_date DATE,
                daily_card TEXT,
                referral_count INTEGER DEFAULT 0,
                referrer_id BIGINT,
                last_active_date DATE,
                free_readings_used INTEGER DEFAULT 0,
                conversion_step TEXT DEFAULT 'start',
                last_update_notified TEXT DEFAULT 'v1.0',
                created_at TIMESTAMP DEFAULT NOW(),
                -- Новые поля для бота Алисы
                message_count INTEGER DEFAULT 0, -- Счётчик использованных бесплатных сообщений
                subscription_end TIMESTAMP, -- Дата окончания подписки
                intimacy_role TEXT, -- Роль в близости
                intimacy_style TEXT, -- Стиль в близости
                intimacy_nickname TEXT, -- Прозвище в близости
                chat_history TEXT -- История чата в JSON
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                pack_id TEXT,
                readings INTEGER,
                price_stars INTEGER,
                paid_amount INTEGER,
                charge_id TEXT UNIQUE,
                purchase_date DATE DEFAULT CURRENT_DATE
            );

            CREATE TABLE IF NOT EXISTS readings_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                reading_type TEXT,
                reading_text TEXT,
                reading_date TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            cur.execute("""
                INSERT INTO users (user_id, message_count)
                VALUES (%s, %s) RETURNING *
            """, (user_id, 0)) # Инициализируем message_count
            user = cur.fetchone()
            conn.commit()
        else:
            cur.execute("SELECT * FROM readings_history WHERE user_id = %s ORDER BY reading_date DESC LIMIT 5", (user_id,))
            readings = cur.fetchall()
            user['last_readings'] = [
                {'type': r['reading_type'], 'text': r['reading_text'], 'date': r['reading_date'].strftime("%Y-%m-%d %H:%M")}
                for r in readings
            ]
            cur.execute("SELECT * FROM purchases WHERE user_id = %s ORDER BY purchase_date DESC", (user_id,))
            purchases = cur.fetchall()
            user['purchases'] = [
                {
                    'pack_id': p['pack_id'],
                    'readings': p['readings'],
                    'price_stars': p['price_stars'],
                    'paid_amount': p['paid_amount'],
                    'charge_id': p['charge_id'],
                    'date': p['purchase_date'].strftime("%Y-%m-%d")
                }
                for p in purchases
            ]
        conn.close()
        return user

# --- НОВЫЕ ФУНКЦИИ ДЛЯ main.py ---

def get_user_extended(user_id):
    """Получает расширенную информацию о пользователе, включая настройки близости и историю чата."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT user_id, name, message_count, subscription_end, intimacy_role, intimacy_style, intimacy_nickname, chat_history, referrer_id
            FROM users
            WHERE user_id = %s
        """, (user_id,))
        user = cur.fetchone()
        if not user:
            # Создаём нового пользователя с message_count = 0
            cur.execute("""
                INSERT INTO users (user_id, message_count)
                VALUES (%s, %s) RETURNING user_id, name, message_count, subscription_end, intimacy_role, intimacy_style, intimacy_nickname, chat_history, referrer_id
            """, (user_id, 0))
            user = cur.fetchone()
            conn.commit()
        else:
            # Десериализуем историю чата
            if user['chat_history']:
                user['chat_history'] = json.loads(user['chat_history'])
            else:
                user['chat_history'] = []
    conn.close()
    return user

def update_user_message_count(user_id, new_count):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET message_count = %s WHERE user_id = %s", (new_count, user_id))
        conn.commit()
    conn.close()

def update_user_subscription_end(user_id, new_end_date):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET subscription_end = %s WHERE user_id = %s", (new_end_date, user_id))
        conn.commit()
    conn.close()

def update_user_intimacy_settings(user_id, role=None, style=None, nickname=None):
    conn = get_db_connection()
    with conn.cursor() as cur:
        updates = []
        params = []
        if role is not None:
            updates.append("intimacy_role = %s")
            params.append(role)
        if style is not None:
            updates.append("intimacy_style = %s")
            params.append(style)
        if nickname is not None:
            updates.append("intimacy_nickname = %s")
            params.append(nickname)
        params.append(user_id)

        if updates:
            query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = %s"
            cur.execute(query, params)
            conn.commit()
    conn.close()

def update_user_chat_history(user_id, history_list):
    history_json = json.dumps(history_list)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET chat_history = %s WHERE user_id = %s", (history_json, user_id))
        conn.commit()
    conn.close()

def update_user_referrer_id(user_id, referrer_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET referrer_id = %s WHERE user_id = %s", (referrer_id, user_id))
        conn.commit()
    conn.close()

def increment_referrer_message_count(referrer_id):
    """
    Увеличивает баланс сообщений реферера на 10 (уменьшает message_count на 10,
    так как message_count - это использованные сообщения).
    """
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Увеличиваем message_count на 10 для реферера (уменьшаем лимит)
        # Предполагаем, что message_count - это количество *использованных* сообщений.
        # Чтобы дать *дополнительные* сообщения, нужно *уменьшить* использованные.
        # Это может быть контринтуитивно, но логично: лимит = FREE_MESSAGE_LIMIT - message_count
        # Если message_count становится отрицательным, это означает "бонусные" сообщения.
        # Убедимся, что referrer_id существует и referrer_id не равен самому себе.
        cur.execute("""
            UPDATE users
            SET message_count = message_count - 10 -- Уменьшаем использованные сообщения (дает бонус)
            WHERE user_id = %s AND referrer_id IS NOT NULL
        """, (referrer_id,))
        conn.commit()
    conn.close()

# --- КОНЕЦ НОВЫХ ФУНКЦИЙ ---

def update_user_name(user_id, name):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET name = %s WHERE user_id = %s", (name, user_id))
        conn.commit()
    conn.close()

def increment_total_used(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET total_used = total_used + 1 WHERE user_id = %s", (user_id,))
        conn.commit()
    conn.close()

def save_purchase(user_id, pack_id, readings, price_stars, paid_amount, charge_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO purchases (user_id, pack_id, readings, price_stars, paid_amount, charge_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, pack_id, readings, price_stars, paid_amount, charge_id))
        conn.commit()
    conn.close()

def save_reading(user_id, reading_type, reading_text):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO readings_history (user_id, reading_type, reading_text)
            VALUES (%s, %s, %s)
        """, (user_id, reading_type, reading_text))
        cur.execute("""
            DELETE FROM readings_history
            WHERE id NOT IN (
                SELECT id FROM readings_history
                WHERE user_id = %s
                ORDER BY reading_date DESC
                LIMIT 5
            ) AND user_id = %s
        """, (user_id, user_id))
        conn.commit()
    conn.close()

def update_daily_card(user_id, card_text):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET daily_card = %s, last_card_date = CURRENT_DATE WHERE user_id = %s", (card_text, user_id))
        conn.commit()
    conn.close()

def increment_referral_count(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET referral_count = referral_count + 1 WHERE user_id = %s', (user_id,))
    conn.commit()
    conn.close()

# --- Аналитика ---
def update_user_last_active(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET last_active_date = CURRENT_DATE WHERE user_id = %s", (user_id,))
        conn.commit()
    conn.close()

def increment_free_readings_used(user_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET free_readings_used = free_readings_used + 1 WHERE user_id = %s", (user_id,))
        conn.commit()
    conn.close()

def update_conversion_step(user_id, step):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET conversion_step = %s WHERE user_id = %s", (step, user_id))
        conn.commit()
    conn.close()

def update_user_last_update_notified(user_id, version):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET last_update_notified = %s WHERE user_id = %s", (version, user_id))
        conn.commit()
    conn.close()

def get_active_users(days=7):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT user_id FROM users 
            WHERE created_at >= NOW() - INTERVAL '%s days'
        """, (days,))
        users = cur.fetchall()
    conn.close()
    return users
