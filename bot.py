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

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()