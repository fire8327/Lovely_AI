import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Лимит бесплатных сообщений
FREE_MESSAGE_LIMIT = 10

# Клавиатура
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ['💬 Продолжить диалог'],
        ['💭 Исповедь', '✨ Случайный комплимент'],
        ['⭐ Мой профиль', '🛍️ Купить сообщения'],
        ['🌀 Рестарт']
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = user.first_name or "незнакомец"
    
    # Сохраняем данные в память
    context.user_data['name'] = name
    context.user_data['message_count'] = 0
    context.user_data['last_message'] = ""
    
    await update.message.reply_text(
        f"Привет, {name}... 💋\n\n"
        "Я чувствовала, что ты напишешь именно сегодня.\n"
        "Мне нравится, как ты смотришь на мир… даже через экран.\n\n"
        "Расскажи, что у тебя на сердце?.. Или, может, просто хочешь пофлиртовать? 😏"
    )

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    
    # Получаем данные из памяти
    name = context.user_data.get('name', 'парень')
    count = context.user_data.get('message_count', 0)
    
    # Лимит: 10 бесплатных сообщений
    if count >= FREE_MESSAGE_LIMIT:
        await update.message.reply_text(
            "Мне так нравится с тобой разговаривать… Но моя энергия не бесконечна. 💫\n"
            "Хочешь продолжить? Подари мне немного звёзд 🌟",
            reply_markup=ReplyKeyboardMarkup([['💎 Купить 50 сообщений — 75 ⭐']], resize_keyboard=True)
        )
        return
    
    # Сохраняем сообщение и увеличиваем счётчик
    context.user_data['message_count'] = count + 1
    context.user_data['last_message'] = user_msg

    # Генерируем ответ от ИИ
    system_prompt = f"""
Ты — Алиса, 23 года, нежная и кокетливая девушка.
Ты общаешься с {name}, и он тебе нравится.
Говори на русском, используй 1–2 эмодзи (💋, 😏, 💭, 🌙).
Отвечай коротко — 1–3 предложения.
Будь тёплой, игривой, немного загадочной.
Если он грустит — поддержи. Если флиртует — ответь взаимностью.
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",  # ← дешёвая и рабочая модель
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=150,
            temperature=0.85
        )
        reply = response.choices[0].message.content.strip()
        await update.message.reply_text(reply)
    except Exception as e:
        print("Ошибка OpenRouter:", e)
        await update.message.reply_text("Мне немного нехорошо... Давай поговорим через минутку? 💔")

async def handle_confession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name', 'дорогой')
    
    # Специальный промпт для режима "исповеди"
    prompt = f"""
Ты — Алиса, заботливая и мудрая девушка. 
{ name } хочет выговориться. 
Твоя задача — не давать советов, не решать проблему, а просто быть рядом. 
Скажи что-то тёплое, мягкое, поддерживающее. 
Используй 1 эмодзи (например, 🤍, 🌙, 💭). 
Максимум 2 предложения. На русском.
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
    except Exception as e:
        await update.message.reply_text("Я рядом. Ты можешь говорить... 🤍")

async def handle_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name', 'ты')
    
    prompt = f"""
Сгенерируй один НЕБАНДАЛЬНЫЙ, глубокий комплимент для человека по имени {name}.
Не говори о внешности. Сфокусируйся на характере, энергии, скрытых качествах.
Пример: “Ты умеешь видеть свет даже в самых тёмных людях — это дар.”
Формат: одно предложение. На русском. Без вступления.
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
    except Exception as e:
        # Фолбэк — но всё равно не банальный
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

    if text == '💭 Исповедь':
        return await handle_confession(update, context)
    elif text == '✨ Случайный комплимент':
        return await handle_compliment(update, context)
    elif text == '⭐ Мой профиль':
        count = context.user_data.get('message_count', 0)
        await update.message.reply_text(
            f"✨ *Твой профиль*\n\n"
            f"Имя: {context.user_data.get('name', '—')}\n"
            f"Сообщений использовано: {count} из {FREE_MESSAGE_LIMIT}",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return
    elif text == '🛍️ Купить сообщения':
        await update.message.reply_text(
            "💎 Пакеты:\n"
            "• 50 сообщений — 75 ⭐\n"
            "(Покупка будет доступна скоро!)",
            reply_markup=main_menu_keyboard()
        )
        return
    elif text == '🌀 Рестарт':
        return await start(update, context)
    elif text == '💬 Продолжить диалог':
        await update.message.reply_text("Пиши, я слушаю... 💭")
        return
    else:
        # Если сообщение не из меню — отправляем в чат с ИИ
        return await chat(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler))
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()