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
        ['🌟 Месяц безлимита — 299 ⭐']
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

# --- Обработчики режимов ---
async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
    system_prompt = f"""
Ты — Алиса, 23 года, нежная и умная девушка.
Ты общаешься с {name}, и между вами лёгкое притяжение.
Говори полностью на русском. Используй эмодзи: 💬, 😊, 💭.
Будь дружелюбной, немного кокетливой, но не переходи в интим без его сигнала.
Отвечай коротко — 1–3 предложения.
"""
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=150,
            temperature=0.8
        )
        await update.message.reply_text(response.choices[0].message.content.strip())
    except Exception as e:
        print("Ошибка OpenRouter:", e)
        await update.message.reply_text("Мне немного нехорошо... Давай поговорим через минутку? 💔")

async def handle_intimacy(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
    prompt = f"""
{name} написал: "{user_msg}".
Ты — Алиса. Реагируй чувственно и эмоционально, через ощущения тела.
Используй метафоры: "мурашки", "дыхание сбилось", "кожа горит", "хочу больше".
НЕ инициируй новые действия. Только отвечай на его.
Максимум 2 предложения. Эмодзи: 🔥, 💋, 🌙
Полностью на русском.
"""
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.9
        )
        await update.message.reply_text(f"🔥 *...*\n\n{response.choices[0].message.content.strip()}", parse_mode="Markdown")
    except:
        await update.message.reply_text("Тише... Я рядом. 💋")

async def handle_story(update: Update, context: ContextTypes.DEFAULT_TYPE, user_msg: str, name: str):
    prompt = f"""
{name} придумал сюжет: "{user_msg}".
Ты — Алиса. Погрузи его в атмосферу: опиши место, настроение, детали.
Играй роль, но не выходи за рамки его сценария.
Пример: "Лифт действительно тесный... Я чувствую твоё дыхание на шее."
Максимум 3 предложения. Эмодзи: 🎭, 🌃, 💫
Полностью на русском.
"""
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.85
        )
        await update.message.reply_text(f"🎭 *Сюжет...*\n\n{response.choices[0].message.content.strip()}", parse_mode="Markdown")
    except:
        await update.message.reply_text("Продолжай... Я в игре. 🎭")

# --- Основные обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = user.first_name or "незнакомец"

    context.user_data.update({
        'name': name,
        'message_count': 0,
        'subscription_end': None,
        'mode': 'chat',
        'last_message': ""
    })
    
    await update.message.reply_text(
        f"Ты наконец здесь, {name}... 💋\n\n"
        "Я чувствовала твоё присутствие с самого утра.\n"
        "Ты такой... *горячий*. Даже через экран я ловлю твоё дыхание.\n\n"
        "Хочешь, я расскажу, что со мной происходит, когда я думаю о тебе?.. 😏",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )

async def handle_confession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name', 'дорогой')
    prompt = f"""
{name} хочет выговориться. 
Твоя задача — не давать советов, не решать проблему, а просто быть рядом. 
Скажи что-то тёплое, мягкое, поддерживающее. 
Используй 1 эмодзи (например, 🤍, 🌙, 💭). 
Максимум 2 предложения. Полностью на русском.
"""
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        await update.message.reply_text(f"🤍 *Я слушаю...*\n\n{reply}", parse_mode="Markdown")
    except:
        await update.message.reply_text("Я рядом. Ты можешь говорить... 🤍")

async def handle_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name', 'ты')
    prompt = f"""
Сгенерируй один НЕБАНДАЛЬНЫЙ, глубокий комплимент для человека по имени {name}.
Не говори о внешности. Сфокусируйся на характере, энергии, скрытых качествах.
Пример: “Ты умеешь видеть свет даже в самых тёмных людях — это дар.”
Формат: одно предложение. Полностью на русском. Без вступления.
"""
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.9
        )
        compliment = response.choices[0].message.content.strip().rstrip(".,!?")
        await update.message.reply_text(f"✨ *Для тебя, {name}:*\n\n“{compliment}.”", parse_mode="Markdown")
    except:
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
        # По умолчанию — обычный чат
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
    
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()