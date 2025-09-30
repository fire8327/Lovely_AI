import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, LabeledPrice
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
Отвечай КРАТКО — максимум 1–2 предложения, без лишних пояснений.
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
                ['🌙 Неделя безлимита — 149 ⭐']
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
            model=model,  # ← можно менять под режим
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
    ai_reply = await call_ai_model(update, context, user_msg, "casual, flirty conversation", model="google/gemma-3-27b-it:free")
    if ai_reply:
        await update.message.reply_text(ai_reply)
        # Сохраняем историю
        history = context.user_data.get('history', [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6:
            history = history[-6:]
        context.user_data['history'] = history
    else:
        await update.message.reply_text("Мне немного нехорошо... Давай поговорим через минутку? 💔")

async def handle_intimacy(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
    ai_reply = await call_ai_model(update, context, user_msg, "sensual, submissive roleplay — focus on physical sensations and obedience", model="google/gemma-3-27b-it:free")
    if ai_reply:
        await update.message.reply_text(f"🔥 *...*\n\n{ai_reply}", parse_mode="Markdown")
        history = context.user_data.get('history', [])
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": ai_reply})
        if len(history) > 6:
            history = history[-6:]
        context.user_data['history'] = history
    else:
        await update.message.reply_text("Жду твоих указаний... 💋")

async def handle_story(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
    ai_reply = await call_ai_model(update, context, user_msg, "immersive storytelling — add one sensory detail to deepen the scene", model="meta-llama/llama-4-maverick:free")
    if ai_reply:
        await update.message.reply_text(f"🎭 *...*\n\n{ai_reply}", parse_mode="Markdown")
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

    if text == '💬 Просто общение':
        context.user_data['mode'] = 'chat'
        await update.message.reply_text("Хорошо... Просто говори со мной. 💬")
        return
    elif text == '🔥 Виртуальная близость':
        context.user_data['mode'] = 'intimacy'
        await update.message.reply_text(
            "Я с тобой... Делай, что хочешь. 🔥\n"
            "(Пиши действия: *раздеваю тебя*, *целую губы*, *ты лежишь подо мной*...)"
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
    elif text == '⬅️ Назад':  # ← обработка кнопки
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