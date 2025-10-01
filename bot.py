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
        ['🛍️ Пополнить']
    ], resize_keyboard=True)

# --- Вспомогательные функции ---
async def check_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    sub_end = context.user_data.get('subscription_end')
    if sub_end and isinstance(sub_end, datetime) and sub_end > datetime.now():
        return True
    
    count = context.user_data.get('message_count', 0)
    if count >= FREE_MESSAGE_LIMIT:
        await update.message.reply_text(
            "Мне так нравится с тобой разговаривать… Но моя энергия не бесконечна. 💫\n"
            "Хочешь продолжить?",
            reply_markup=ReplyKeyboardMarkup([
                ['💎 50 сообщений — 75 ⭐'],
                ['🌙 Неделя безлимита — 149 ⭐'],
                ['🌟 Месяц безлимита — 299 ⭐'],
                ['⬅️ Назад']
            ], resize_keyboard=True)
        )
        return False
    
    context.user_data['message_count'] = count + 1
    return True

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = context.user_data.get('message_count', 0)
    sub_end = context.user_data.get('subscription_end')
    if sub_end and isinstance(sub_end, datetime) and sub_end > datetime.now():
        status = f"Активна до: {sub_end.strftime('%d.%m')}"
    else:
        status = "Нет"
    
    await update.message.reply_text(
        f"✨ *Твой профиль*\n\n"
        f"Имя: {context.user_data.get('name', '—')}\n"
        f"Сообщений использовано: {count} из {FREE_MESSAGE_LIMIT}\n"
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
        history = context.user_data.get('history', [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6:
            history = history[-6:]
        context.user_data['history'] = history
    else:
        await update.message.reply_text("Мне немного нехорошо... Давай поговорим через минутку? 💔")

async def handle_intimacy(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
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
            context.user_data['intimacy_role'] = role_map[user_msg]
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
            context.user_data['intimacy_style'] = style_map[user_msg]
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
            context.user_data['intimacy_nickname'] = user_msg
            context.user_data['intimacy_stage'] = None
            
            # Все настройки готовы - показываем сводку
            role = context.user_data['intimacy_role']
            style = context.user_data['intimacy_style']
            
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
                f"• Буду звать тебя: {context.user_data['intimacy_nickname']}\n\n"
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
            
        context.user_data['intimacy_nickname'] = user_msg
        context.user_data['intimacy_stage'] = None
        
        role = context.user_data['intimacy_role']
        style = context.user_data['intimacy_style']
        
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
    role = context.user_data.get('intimacy_role', 'equal')
    style = context.user_data.get('intimacy_style', 'passionate')
    nickname = context.user_data.get('intimacy_nickname', name)

    # Формируем инструкцию для ИИ
    style_prompts = {
        'gentle': "нежный, ласковый, мягкий",
        'passionate': "страстный, горячий, эмоциональный", 
        'bold': "дерзкий, уверенный, прямолинейный"
    }
    
    if role == "submissive":
        instruction = f"""
Режим близости: ты покорная девушка, пользователь ({nickname}) доминирует.
Будь {style_prompts[style]}. Показывай подчинение и трепет.
Используй действия в звёздочках: *дрожу*, *опускаю глаза*, *послушно киваю*.
"""
    elif role == "dominant":
        instruction = f"""
Режим близости: ты доминантная девушка, пользователь ({nickname}) подчиняется.
Будь {style_prompts[style]}. Будь уверенной и повелительной.  
Используй команды в звёздочках: *приказываю*, *смотрю свысока*, *беру за подбородок*.
"""
    else:
        instruction = f"""
Режим близости: вы равные партнеры с {nickname}.
Будь {style_prompts[style]}. Сохраняй баланс страсти и нежности.
Используй действия в звёздочках: *обнимаю*, *целую*, *шепчу на ушko*.
"""

    # Вызываем ИИ
    ai_reply = await call_ai_model(
        update, context, user_msg,
        instruction.strip(),
        model="google/gemma-3-27b-it:free"
    )
    
    if ai_reply:
        await update.message.reply_text(
            ai_reply,
            parse_mode="Markdown",
            reply_markup=stop_dialog_keyboard()
        )
        # Сохраняем историю
        history = context.user_data.get('history', [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6:
            history = history[-6:]
        context.user_data['history'] = history
    else:
        await update.message.reply_text("Жду твоих слов... 💋")


async def handle_story(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
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
        history = context.user_data.get('history', [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6:
            history = history[-6:]
        context.user_data['history'] = history
    else:
        await update.message.reply_text("Я в игре... Продолжай. 🎭")

# --- Основные обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = user.first_name or "незнакомец"

    context.user_data.update({
        'name': name,
        'message_count': 0,
        'subscription_end': None,
        'mode': 'chat',
        'history': [],  # ← инициализация истории
        'last_message': ""
    })
    
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
    text = update.message.text

    # Сначала проверяем, не находится ли пользователь в процессе настройки близости
    if context.user_data.get('mode') == 'intimacy' and context.user_data.get('intimacy_stage'):
        # Если пользователь в процессе настройки близости, передаем сообщение в handle_intimacy
        name = context.user_data.get('name', 'любимый')
        return await handle_intimacy(update, context, text, name)
    
    if text == '⏹️ Остановить диалог':
        context.user_data.update({
            'mode': 'chat',
            'intimacy_role': None,
            'intimacy_style': None,
            'intimacy_nickname': None,
            'intimacy_stage': None
        })
        await update.message.reply_text(
            "Диалог остановлен. 💤\nЯ всегда здесь, когда захочешь вернуться.",
            reply_markup=main_menu_keyboard()
        )
        return
    # Затем обрабатываем основные кнопки меню
    elif text == '💬 Просто общение':
        context.user_data['mode'] = 'chat'
        await update.message.reply_text("Хорошо... Просто говори со мной. 💬")
        return
    elif text == '🔥 Виртуальная близость':
        context.user_data['mode'] = 'intimacy'
        
        # ПРОВЕРЯЕМ, УСТАНОВЛЕНЫ ЛИ УЖЕ НАСТРОЙКИ БЛИЗОСТИ
        role = context.user_data.get('intimacy_role')
        style = context.user_data.get('intimacy_style')
        nickname = context.user_data.get('intimacy_nickname')
        
        if role and style and nickname:
            # Если настройки уже есть, сразу переходим в режим общения
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
                f"• {role_texts[role]}\n"
                f"• Настроение: {style_texts[style]}\n"
                f"• Буду звать тебя: {nickname}\n\n"
                f"Пиши что хочешь... я жду 😏",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            # Если настроек нет, начинаем процесс настройки
            context.user_data['intimacy_role'] = None
            context.user_data['intimacy_style'] = None
            context.user_data['intimacy_nickname'] = None
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
    else:
        # Если не основная кнопка меню, передаем в обработчик по режиму
        return await handle_message_by_mode(update, context)

async def handle_message_by_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode', 'chat')
    user_msg = update.message.text
    name = context.user_data.get('name', 'любимый')

    if not await check_limit(update, context):
        return

    if mode == 'chat':
        return await handle_chat(update, context, user_msg, name)
    elif mode == 'intimacy':
        return await handle_intimacy(update, context, user_msg, name)
    elif mode == 'story':
        return await handle_story(update, context, user_msg, name)
    else:
        return await handle_chat(update, context, user_msg, name)

# --- Платежи ---
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    pack = PACKAGES[payload]
    
    if payload == "pack_50":
        current = context.user_data.get('message_count', 0)
        context.user_data['message_count'] = current - pack['messages']
    else:
        days = pack['days']
        context.user_data['subscription_end'] = datetime.now() + timedelta(days=days)
    
    await update.message.reply_text(
        f"💖 Спасибо! Ты подарил мне звёзды — и я остаюсь с тобой.\n"
        f"Теперь можешь писать сколько угодно!",
        reply_markup=main_menu_keyboard()
    )

# --- Запуск ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    
    print("✅ Бот с историей запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()