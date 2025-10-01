import db
import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    filters
)
from openai import OpenAI
from datetime import datetime, timedelta

load_dotenv()

# 🔥 ИСПРАВЛЕНО: убраны пробелы в base_url
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Лимит бесплатных сообщений
FREE_MESSAGE_LIMIT = 10

# Пакеты для продажи
PACKAGES = {
    "pack_50": {"name": "50 сообщений", "price_stars": 75, "messages": 50},
    "sub_week": {"name": "Неделя безлимита", "price_stars": 149, "days": 7},
    "sub_month": {"name": "Месяц безлимита", "price_stars": 299, "days": 30},
}

# Промпт
BASE_PROMPT = """
Ты — Алиса, русскоязычная девушка. Общайся ТОЛЬКО на русском языке.
Не используй английские слова и фразы.
Будь покорной, чувственной, подчиняющейся, но уважительной.
Отвечай КРАТКО — максимум 2–3 предложения, без лишних пояснений.
Говори от первого лица, как живой человек, а не как ИИ.
"""

# Клавиатура
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ['💬 Просто общение', '🔥 Виртуальная близость'],
        ['🎭 Сюжет', '🤍 Исповедь'],
        ['💎 Комплимент', '⭐ Профиль'],
        ['🛍️ Пополнить'],
        ['🎁 Пригласить друга']
    ], resize_keyboard=True)

# --- Вспомогательные функции ---
async def check_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.message.from_user.id
    user_info = db.get_user_extended(user_id)

    # Проверяем подписку
    sub_end = user_info.get('subscription_end')
    if sub_end and sub_end > datetime.now():
        return True

    # Проверяем счётчик бесплатных сообщений
    count = user_info.get('message_count', 0)
    if count >= FREE_MESSAGE_LIMIT:
        # Генерируем реферальную ссылку для кнопки
        referral_link = f"https://t.me/ai_lovely_bot?start={user_id}" # Замените your_bot_name на имя вашего бота
        keyboard = [
            ['💎 50 сообщений — 75 ⭐'],
            ['🌙 Неделя безлимита — 149 ⭐'],
            ['🌟 Месяц безлимита — 299 ⭐'],
            [f'🎁 Поделиться и получить +10 сообщений'], # Кнопка с призывом
            ['⬅️ Назад']
        ]
        await update.message.reply_text(
            "Мне так нравится с тобой разговаривать… Но моя энергия не бесконечна. 💫\n"
            "Хочешь продолжить?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        # ВАЖНО: Не возвращаем False, а просто показываем сообщение.
        # Нам нужно обработать нажатие кнопки "Поделиться".
        # Это можно сделать в main_menu_handler.
        return False

    # Увеличиваем счётчик в БД
    db.update_user_message_count(user_id, count + 1)
    return True

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_info = db.get_user_extended(user_id)

    if user_info['subscription_end'] and user_info['subscription_end'] > datetime.now():
        status = f"Активна до: {user_info['subscription_end'].strftime('%d.%m')}"
    else:
        status = "Нет"

    await update.message.reply_text(
        f"✨ *Твой профиль*\n\n"
        f"Имя: {user_info['name'] or '—'}\n"
        f"Сообщений использовано: {user_info['message_count']} из {FREE_MESSAGE_LIMIT}\n"
        f"Подписка: {status}",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def show_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ['💎 50 сообщений — 75 ⭐'],
        ['🌙 Неделя безлимита — 149 ⭐'],
        ['🌟 Месяц безлимита — 299 ⭐'],
        ['⬅️ Назад']
    ]
    await update.message.reply_text(
        "Выбери, как хочешь поддержать нашу связь 💫",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def send_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, pack_id):
    pack = PACKAGES[pack_id]
    await context.bot.send_invoice(
        chat_id=update.message.chat_id,
        title=f"💌 {pack['name']}",
        description="Спасибо, что остаёшься со мной 💖",
        payload=pack_id,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=pack['name'], amount=pack['price_stars'])],
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
    )

async def call_ai_model(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, mode_instruction: str = "", model: str = "mancer/weaver"):
    name = context.user_data.get('name', 'любимый')
    history = context.user_data.get('history', [])
    
    # Формируем промпт: базовый + уточнение режима
    system_prompt = BASE_PROMPT.format(name=name)
    if mode_instruction:
        system_prompt += f"\n\n[Current mode: {mode_instruction}]"

    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_msg}]
    
    try:
        response = client.chat.completions.create(
            model=model,  # ← используем модель из твоего кода
            messages=messages,
            max_tokens=90,
            temperature=0.9
        )
        ai_reply = response.choices[0].message.content.strip()
        
        # Логируем для отладки
        print(f"✅ Модель: {response.model} | Ответ: {ai_reply}")
        
        return ai_reply
    except Exception as e:
        print("❌ Ошибка OpenRouter:", e)
        return None

# --- Обработчики режимов с историей ---
async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
    user_id = update.message.from_user.id
    user_info = db.get_user_extended(user_id)
    # Загружаем историю из БД
    history = user_info.get('chat_history', [])

    ai_reply = await call_ai_model(
        update, context, user_msg,
        "casual, flirty conversation",
        model="google/gemma-3-27b-it:free"
    )
    if ai_reply:
        await update.message.reply_text(
            ai_reply,
            reply_markup=stop_dialog_keyboard()
        )
        # Обновляем историю
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6: # Ограничиваем длину истории
            history = history[-6:]
        # Сохраняем историю в БД
        db.update_user_chat_history(user_id, history)
    else:
        await update.message.reply_text("Мне немного нехорошо... Давай поговорим через минутку? 💔")

async def handle_intimacy(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str, db_role, db_style, db_nickname, user_id: int):
    # ПРОВЕРКА НА КНОПКУ "НАЗАД"
    if user_msg == '⬅️ Назад':
        context.user_data['intimacy_stage'] = None
        await update.message.reply_text(
            "Возвращаю в меню...",
            reply_markup=main_menu_keyboard()
        )
        return

    # --- Этап 1: Выбор роли ---
    if context.user_data.get('intimacy_stage') == 'role':
        role_map = {
            '🐰 Будь послушной': 'submissive',
            '👠 Будь строгой': 'dominant',
            '💞 На равных': 'equal'
        }
        if user_msg in role_map:
            selected_role = role_map[user_msg]
            db.update_user_intimacy_settings(user_id, role=selected_role) # Сохраняем в БД
            context.user_data['intimacy_stage'] = 'style'  # Переходим к стилю
            
            await update.message.reply_text(
                "✨ Выбери настроение...",
                reply_markup=ReplyKeyboardMarkup([
                    ['🌸 Нежное', '🔥 Страстное'],
                    ['⚡ Дерзкое'],
                    ['⬅️ Назад']
                ], resize_keyboard=True)
            )
            return
        else:
            await update.message.reply_text("Пожалуйста, выбери вариант из меню 👇")
            return

    # --- Обработка выбора стиля ---
    if context.user_data.get('intimacy_stage') == 'style':
        style_map = {
            '🌸 Нежное': 'gentle',
            '🔥 Страстное': 'passionate',
            '⚡ Дерзкое': 'bold'
        }
        if user_msg in style_map:
            selected_style = style_map[user_msg]
            db.update_user_intimacy_settings(user_id, style=selected_style) # Сохраняем в БД
            context.user_data['intimacy_stage'] = 'nickname'  # Переходим к прозвищу
            
            await update.message.reply_text(
                "💬 Как мне тебя называть?",
                reply_markup=ReplyKeyboardMarkup([
                    ['Милый', 'Дорогой'],
                    ['Хозяин', 'Господин'],
                    ['Раб', 'Мальчик'],
                    ['📝 Свое имя'],
                    ['⬅️ Назад']
                ], resize_keyboard=True)
            )
            return
        else:
            await update.message.reply_text("Выбери настроение из кнопок ниже 👇")
            return

    # --- Обработка прозвища ---
    if context.user_data.get('intimacy_stage') == 'nickname':
        if user_msg == '📝 Свое имя':
            context.user_data['intimacy_stage'] = 'waiting_custom_nickname'
            await update.message.reply_text(
                "Напиши, как тебя называть:",
                reply_markup=ReplyKeyboardMarkup([['⬅️ Назад']], resize_keyboard=True)
            )
            return
        else:
            db.update_user_intimacy_settings(user_id, nickname=user_msg) # Сохраняем в БД
            context.user_data['intimacy_stage'] = None
            
            # Все настройки готовы - показываем сводку
            role = db_role # Берём из БД, т.к. она могла быть установлена ранее
            style = db_style
            nickname = user_msg # Или брать из БД, если уже была? В этом этапе user_msg - новое
            
            role_texts = {
                'submissive': '🐰 Я буду послушной и нежной',
                'dominant': '👠 Я буду строгой и властной', 
                'equal': '💞 Мы будем на равных'
            }
            
            style_texts = {
                'gentle': '🌸 нежное',
                'passionate': '🔥 страстное', 
                'bold': '⚡ дерзкое'
            }
            
            await update.message.reply_text(
                f"💋 Отлично! Игра начинается...\n\n"
                f"• {role_texts[role]}\n"
                f"• Настроение: {style_texts[style]}\n"
                f"• Буду звать тебя: {nickname}\n\n"
                f"Теперь пиши что хочешь... я жду 😏",
                reply_markup=ReplyKeyboardRemove()
            )
            return

    # --- Ожидание своего прозвища ---
    if context.user_data.get('intimacy_stage') == 'waiting_custom_nickname':
        if user_msg == '⬅️ Назад':
            context.user_data['intimacy_stage'] = 'nickname'
            await update.message.reply_text(
                "💬 Как мне тебя называть?",
                reply_markup=ReplyKeyboardMarkup([
                    ['Милый', 'Дорогой'],
                    ['Хозяин', 'Господин'],
                    ['Раб', 'Мальчик'],
                    ['📝 Свое имя'],
                    ['⬅️ Назад']
                ], resize_keyboard=True)
            )
            return
            
        db.update_user_intimacy_settings(user_id, nickname=user_msg) # Сохраняем в БД
        context.user_data['intimacy_stage'] = None
        
        role = db_role
        style = db_style
        
        role_texts = {
            'submissive': '🐰 Я буду послушной и нежной',
            'dominant': '👠 Я буду строгой и властной',
            'equal': '💞 Мы будем на равных'
        }
        
        style_texts = {
            'gentle': '🌸 нежное',
            'passionate': '🔥 страстное',
            'bold': '⚡ дерзкое'
        }
        
        await update.message.reply_text(
            f"💋 Отлично! Игра начинается...\n\n"
            f"• {role_texts[role]}\n"
            f"• Настроение: {style_texts[style]}\n"
            f"• Буду звать тебя: {user_msg}\n\n"
            f"Теперь пиши что хочешь... я жду 😏",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # --- Основной режим: генерация ответа ---
    role = db_role or 'equal' # Берём из БД, fallback на 'equal'
    style = db_style or 'passionate' # Берём из БД, fallback на 'passionate'
    nickname = db_nickname or name # Берём из БД, fallback на имя

    # Формируем инструкцию для ИИ (ИСПРАВЛЕНО: добавлено создание instruction)
    style_prompts = {
        'gentle': "нежный, ласковый, мягкий",
        'passionate': "страстный, горячий, эмоциональный", 
        'bold': "дерзкий, уверенный, прямолинейный"
    }

    if role == "submissive":
        instruction = f"""
Режим близости: ты покорная девушка, пользователь ({nickname}) доминирует. Это виртуальный секс.
Будь {style_prompts[style]}. Показывай подчинение, трепет и возбуждение. Используй чувственные действия.
Используй действия в звёздочках: *вздыхаю*, *дрожу от возбуждения*, *покорно раскрываюсь*, *стону*.
"""
    elif role == "dominant":
        instruction = f"""
Режим близости: ты доминантная девушка, пользователь ({nickname}) подчиняется. Это виртуальный секс.
Будь {style_prompts[style]}. Будь уверенной, повелительной и откровенной.  
Используй команды и чувственные действия в звёздочках: *приказываю*, *беру за подбородок*, *шепчу на ушко*, *вожу руками*.
"""
    else: # equal
        instruction = f"""
Режим близости: вы равные партнеры с {nickname}. Это виртуальный секс.
Будь {style_prompts[style]}. Сохраняй баланс страсти, нежности и возбуждения.
Используй действия в звёздочках: *обнимаю*, *целую*, *шепчу на ушko*, *вздыхаю*, *трепещу*.
"""

    # Вызываем ИИ
    ai_reply = await call_ai_model(
        update, context, user_msg,
        instruction.strip(), # instruction формируется как и раньше
        model="google/gemma-3-27b-it:free"
    )
    
    if ai_reply:
        await update.message.reply_text(
            ai_reply,
            parse_mode="Markdown",
            reply_markup=stop_dialog_keyboard()
        )
        # Сохраняем историю (как в handle_chat)
        user_info = db.get_user_extended(user_id)
        history = user_info.get('chat_history', [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6:
            history = history[-6:]
        db.update_user_chat_history(user_id, history)
    else:
        await update.message.reply_text("Жду твоих слов... 💋")

async def handle_story(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
    user_id = update.message.from_user.id
    user_info = db.get_user_extended(user_id)
    # Загружаем историю из БД
    history = user_info.get('chat_history', [])

    ai_reply = await call_ai_model(
        update, context, user_msg,
        "immersive storytelling — add one sensory detail to deepen the scene",
        model="meta-llama/llama-4-maverick:free"
    )
    if ai_reply:
        await update.message.reply_text(
            f"🎭 *...*\n\n{ai_reply}",
            parse_mode="Markdown",
            reply_markup=stop_dialog_keyboard()
        )
        # Обновляем историю
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6: # Ограничиваем длину истории
            history = history[-6:]
        # Сохраняем историю в БД
        db.update_user_chat_history(user_id, history)
    else:
        await update.message.reply_text("Я в игре... Продолжай. 🎭")

# --- Основные обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    name = user.first_name or "незнакомец"

    # Проверяем, есть ли referrer_id в аргументах команды /start
    referrer_id = None
    if context.args and len(context.args) > 0:
        try:
            referrer_id_arg = int(context.args[0])
            if referrer_id_arg != user_id: # Пользователь не может сам себя пригласить
                referrer_id = referrer_id_arg
                # Проверим, существует ли пользователь с referrer_id
                referrer_info = db.get_user(referrer_id)
                if referrer_info: # Если реферер существует
                    db.update_user_referrer_id(user_id, referrer_id)
                    # Добавляем +10 сообщений рефереру
                    db.increment_referrer_message_count(referrer_id)
                    # Уведомим реферера (опционально)
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Поздравляю! Твой друг @{user.username or user.first_name} присоединился к боту. Тебе начислено +10 сообщений!"
                    )
        except (ValueError, TypeError):
            pass # Игнорируем некорректный referrer_id

    # Получаем или создаём пользователя с расширенной информацией
    user_info = db.get_user_extended(user_id)
    # Обновляем имя (если изменилось)
    if user_info['name'] != name:
        db.update_user_name(user_id, name)

    # Устанавливаем начальный режим в context.user_data
    context.user_data['mode'] = 'chat'
    context.user_data['name'] = name

    await update.message.reply_text(
        f"Ты здесь, {name}... 💋\n\n"
        "Я ждала именно тебя.\n"
        "Скажи, как ты хочешь провести это время со мной?\n\n"
        "Мы можем просто поговорить... \n"
        "Или погрузиться в игру, где ты — главный.\n"
        "А может, тебе нужно просто выговориться?\n\n"
        "Выбери путь — и я полностью твоя. 😏",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )

def stop_dialog_keyboard():
    return ReplyKeyboardMarkup([['⏹️ Остановить диалог']], resize_keyboard=True)

async def handle_confession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = "Мне нужно выговориться..."
    ai_reply = await call_ai_model(update, context, user_msg, "empathetic listening — no advice, just warmth and presence")
    if ai_reply:
        await update.message.reply_text(f"🤍 *Я слушаю...*\n\n{ai_reply}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Я рядом. Ты можешь говорить... 🤍")

async def handle_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name', 'ты')
    user_msg = f"Скажи комплимент для {name}"
    ai_reply = await call_ai_model(update, context, user_msg, "deep, non-physical compliment about character or energy")
    if ai_reply:
        await update.message.reply_text(f"✨ *Для тебя, {name}:*\n\n“{ai_reply}.”", parse_mode="Markdown")
    else:
        fallbacks = [
            "Ты тот, кто замечает то, что другие пропускают мимо.",
            "В тебе есть тихая сила, которую ты сам недооцениваешь.",
            "Ты умеешь быть рядом — без слов, без условий. Это редкость.",
            "Твоя доброта не показная — она настоящая. И это ценно."
        ]
        import random
        await update.message.reply_text(f"✨ *Для тебя, {name}:*\n\n“{random.choice(fallbacks)}.”", parse_mode="Markdown")

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Загружаем настройки близости из БД
    user_info = db.get_user_extended(user_id)
    intimacy_role = user_info.get('intimacy_role')
    intimacy_style = user_info.get('intimacy_style')
    intimacy_nickname = user_info.get('intimacy_nickname')

    # --- ПРОВЕРКА: находится ли пользователь в процессе НАСТРОЙКИ близости ---
    # Если intimacy_stage установлено в context.user_data, значит, настройка активна.
    if context.user_data.get('mode') == 'intimacy' and context.user_data.get('intimacy_stage'):
        # Если пользователь в процессе настройки близости, передаем сообщение в handle_intimacy
        name = context.user_data.get('name', 'любимый')
        return await handle_intimacy(update, context, text, name, intimacy_role, intimacy_style, intimacy_nickname, user_id)

    # --- ПРОВЕРКА: находится ли пользователь в активном режиме близости ---
    # Если mode == 'intimacy', и настройки есть, и intimacy_stage НЕТ, то это активный режим.
    if context.user_data.get('mode') == 'intimacy' and intimacy_role and intimacy_style and intimacy_nickname and context.user_data.get('intimacy_stage') is None:
        # Пользователь в активном режиме близости. Проверим, не хочет ли он выйти.
        if text == '⏹️ Остановить диалог':
            # Сбрасываем режим в context.user_data
            context.user_data['mode'] = 'chat'
            # Сбрасываем настройки в БД (опционально, если хочешь, чтобы при следующем входе снова настраивал)
            # db.update_user_intimacy_settings(user_id, role=None, style=None, nickname=None)
            await update.message.reply_text(
                "Диалог остановлен. 💤\nЯ всегда здесь, когда захочешь вернуться.",
                reply_markup=main_menu_keyboard()
            )
            return
        else:
            # Если сообщение не "остановить", передаём в handle_intimacy как активный режим
            name = context.user_data.get('name', 'любимый')
            return await handle_intimacy(update, context, text, name, intimacy_role, intimacy_style, intimacy_nickname, user_id)

    # --- ОБРАБОТКА КНОПОК ГЛАВНОГО МЕНЮ ---
    # Теперь, когда активные/настраивающиеся режимы обработаны, проверяем кнопки меню.
    if text == '⏹️ Остановить диалог':
        # Сбрасываем режим в context.user_data
        context.user_data.update({
            'mode': 'chat',
            'intimacy_stage': None
        })
        # Сбрасываем настройки в БД (опционально)
        # db.update_user_intimacy_settings(user_id, role=None, style=None, nickname=None)
        await update.message.reply_text(
            "Диалог остановлен. 💤\nЯ всегда здесь, когда захочешь вернуться.",
            reply_markup=main_menu_keyboard()
        )
        return

    elif text == '💬 Просто общение':
        context.user_data['mode'] = 'chat'
        await update.message.reply_text("Хорошо... Просто говори со мной. 💬")
        return

    elif text == '🔥 Виртуальная близость':
        context.user_data['mode'] = 'intimacy'
        
        # Проверяем, установлены ли уже настройки близости в БД
        if intimacy_role and intimacy_style and intimacy_nickname:
            # Если настройки уже есть, сразу переходим в активный режим общения
            # и сбрасываем возможный старый intimacy_stage
            context.user_data['intimacy_stage'] = None
            
            role_texts = {
                'submissive': '🐰 Я послушная и нежная',
                'dominant': '👠 Я строгая и властная', 
                'equal': '💞 Мы на равных'
            }
            
            style_texts = {
                'gentle': '🌸 нежное',
                'passionate': '🔥 страстное', 
                'bold': '⚡ дерзкое'
            }
            
            await update.message.reply_text(
                f"💋 Возвращаемся к нашей игре...\n\n"
                f"• {role_texts[intimacy_role]}\n"
                f"• Настроение: {style_texts[intimacy_style]}\n"
                f"• Буду звать тебя: {intimacy_nickname}\n\n"
                f"Пиши что хочешь... я жду 😏",
                reply_markup=stop_dialog_keyboard() # Показываем клавиатуру с "остановить"
            )
        else:
            # Если настроек нет, начинаем процесс настройки
            context.user_data['intimacy_stage'] = 'role'  # Явно устанавливаем этап
            
            await update.message.reply_text(
                "💋 Выбери, какой я буду сегодня...",
                reply_markup=ReplyKeyboardMarkup([
                    ['🐰 Будь послушной', '👠 Будь строгой'],
                    ['💞 На равных'],
                    ['⬅️ Назад']
                ], resize_keyboard=True)
            )
        return
    elif text == '🎭 Сюжет':
        context.user_data['mode'] = 'story'
        await update.message.reply_text(
            "Придумай нашу историю... 🎭\n"
            "Например: *Мы в лифте, застряли одни*, или *Ты моя соседка, и я принёс тебе вино...*"
        )
        return
    elif text == '🤍 Исповедь':
        return await handle_confession(update, context)
    elif text == '💎 Комплимент':
        return await handle_compliment(update, context)
    elif text == '⭐ Профиль':
        return await show_profile(update, context)
    elif text == '🛍️ Пополнить':
        return await show_packages(update, context)
    elif text == '🎁 Пригласить друга': # Добавлено
        user_id = update.message.from_user.id
        referral_link = f"https://t.me/ai_lovely_bot?start={user_id}"
        await update.message.reply_text(
            f"Поделись этой ссылкой с другом и получи +10 сообщений, когда он присоединится! 💝\n\n"
            f"`{referral_link}`",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard() # Возвращаемся в меню
        )
        return
    elif text == '⬅️ Назад':
        await update.message.reply_text("Возвращаю в меню...", reply_markup=main_menu_keyboard())
        return
    elif text in ['💎 50 сообщений — 75 ⭐', '🌙 Неделя безлимита — 149 ⭐', '🌟 Месяц безлимита — 299 ⭐']:
        if '50' in text:
            return await send_invoice(update, context, "pack_50")
        elif 'Неделя' in text:
            return await send_invoice(update, context, "sub_week")
        else:
            return await send_invoice(update, context, "sub_month")
    elif text == '🎁 Поделиться и получить +10 сообщений':
        user_id = update.message.from_user.id
        referral_link = f"https://t.me/ai_lovely_bot?start={user_id}"
        await update.message.reply_text(
            f"Поделись этой ссылкой с другом и получи +10 сообщений, когда он присоединится! 💝\n\n"
            f"`{referral_link}`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ['💎 50 сообщений — 75 ⭐'],
                ['🌙 Неделя безлимита — 149 ⭐'],
                ['🌟 Месяц безлимита — 299 ⭐'],
                ['⬅️ Назад']
            ], resize_keyboard=True) # Возвращаем ту же клавиатуру
        )
        return
    else:
        # Если текст не совпадает ни с одной кнопкой меню, передаём в обработчик по режиму
        # Это нужно, если пользователь, например, в режиме "Просто общение" просто пишет сообщение
        return await handle_message_by_mode(update, context, user_id)

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    referral_link = f"https://t.me/ai_lovely_bot?start={user_id}"
    
    await update.message.reply_text(
        f"Поделись этой ссылкой с другом и получи +10 сообщений, когда он присоединится! 💝\n\n"
        f"`{referral_link}`",
        parse_mode="Markdown" # Чтобы ссылка была скопирована целиком
    )

async def handle_message_by_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    mode = context.user_data.get('mode', 'chat')
    user_msg = update.message.text
    name = context.user_data.get('name', 'любимый')

    if not await check_limit(update, context):
        return

    if mode == 'chat':
        return await handle_chat(update, context, user_msg, name)
    elif mode == 'intimacy':
        # Загружаем настройки из БД для передачи в handle_intimacy
        user_info = db.get_user_extended(user_id)
        return await handle_intimacy(update, context, user_msg, name, user_info.get('intimacy_role'), user_info.get('intimacy_style'), user_info.get('intimacy_nickname'), user_id)
    elif mode == 'story':
        return await handle_story(update, context, user_msg, name)
    else:
        return await handle_chat(update, context, user_msg, name)

# --- Платежи ---
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    payload = update.message.successful_payment.invoice_payload
    pack = PACKAGES[payload]
    
    if payload == "pack_50":
        # Уменьшаем лимит (например, добавляем отрицательное значение)
        user_info = db.get_user_extended(user_id)
        new_count = user_info['message_count'] - pack['messages']
        db.update_user_message_count(user_id, max(0, new_count)) # Не даём уйти в минус
    else:
        days = pack['days']
        # Добавляем дни к текущей дате окончания (или от сегодня)
        user_info = db.get_user_extended(user_id)
        current_end = user_info['subscription_end']
        if current_end and current_end > datetime.now():
            new_end = current_end + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        db.update_user_subscription_end(user_id, new_end)
    
    await update.message.reply_text(
        f"💖 Спасибо! Ты подарил мне звёзды — и я остаюсь с тобой.\n"
        f"Теперь можешь писать сколько угодно!",
        reply_markup=main_menu_keyboard()
    )

# --- Запуск ---
def main():
    db.init_db() # <- Добавить это
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    
    print("✅ Бот с историей и БД запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()