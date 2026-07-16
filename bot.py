"""
BALA LAB — Telegram-бот Алем с ИИ 🌱
"""
import logging
import os
import anthropic
from datetime import datetime, time
from certificate import generate_certificate
from gtts import gTTS
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from database import Database
from content import FACTS, PLANTS, ACHIEVEMENTS, STEPS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db = Database(os.getenv("DATABASE_URL"))
ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

IMG_ALEM = "AgACAgIAAxkBAAPcakeo6as2BBcXFqUj2BgzDGl0rcoAAikZaxslAkBK6jf4ulAWKg8BAAMCAAN5AAM8BA"
IMG_SPROUTS = "AgACAgIAAxkBAAPdakeo6c-zHl-E4tYpIMgCiOaFnbQAAi0ZaxslAkBKzHmdMl-XWTUBAAMCAAN5AAM8BA"
IMG_WATER = "AgACAgIAAxkBAAPeakeo6ZLRcAdZpCFRr_426c3CP4oAAiwZaxslAkBKG2juMJendGgBAAMCAAN5AAM8BA"
IMG_HARVEST = "AgACAgIAAxkBAAPfakeo6YGz2cT1auqNESsfVokyGNUAAisZaxslAkBKYh9KXWvdC0ABAAMCAAN5AAM8BA"

SYSTEM_PROMPT = """Ты Алем — дружелюбный ИИ-помощник для детей 6+ из набора BALA LAB Microgreens.
Помогаешь выращивать микрозелень (горох, редис, брокколи). Отвечай коротко (2-4 предложения), весело, на русском. Используй эмодзи.
Контекст: {USER_CONTEXT}"""

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💧 Полить"), KeyboardButton("📏 Записать рост")],
        [KeyboardButton("📒 Мой дневник"), KeyboardButton("🌿 Факт дня")],
        [KeyboardButton("🏆 Достижения"), KeyboardButton("📋 Инструкция")],
    ], resize_keyboard=True)

def plant_keyboard():
    buttons = [[InlineKeyboardButton(f"{v['emoji']} {k}", callback_data=f"plant_{k}")] for k, v in PLANTS.items()]
    buttons.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)

def diary_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 График роста", callback_data="chart"),
         InlineKeyboardButton("📝 Заметка", callback_data="note")],
        [InlineKeyboardButton("🗓 История", callback_data="history")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.register_user(user.id, user.first_name)
    context.user_data.clear()
    await update.message.reply_photo(
        photo=IMG_ALEM,
        caption=(
            f"Привет, {user.first_name}! 👋\n\n"
            "Я Алем — ИИ-помощник из набора BALA LAB Microgreens ✨🌱\n\n"
            "Вместе мы будем:\n"
            "🌱 Выращивать микрозелень\n"
            "🤖 Отвечать на любые вопросы\n"
            "📊 Вести дневник наблюдений\n"
            "🏆 Получать достижения!\n\n"
            "Выбери культуру для посева 👇"
        ),
        reply_markup=main_keyboard()
    )
    await update.message.reply_text("Какие семена сеешь? 🌱", reply_markup=plant_keyboard())

async def choose_plant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plant_name = query.data.replace("plant_", "")
    plant = PLANTS[plant_name]
    db.start_experiment(query.from_user.id, plant_name)
    await query.edit_message_text(
        f"{plant['emoji']} {plant_name} — эксперимент начат!\n\n"
        f"⏱ Прорастание: {plant['sprout_days']} дня\n"
        f"🥗 Урожай через: {plant['harvest_days']} дней\n\n"
        f"💡 Факт: {plant['fact']}\n\n"
        f"Задавай мне любые вопросы! 🔬"
    )

async def cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Выбери культуру позже через /start 🌱")

async def water(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exp = db.get_experiment(user_id)
    if not exp:
        await update.message.reply_text("Сначала начни эксперимент! Нажми /start 🌱", reply_markup=main_keyboard())
        return

    day = db.get_experiment_day(user_id)
    plant = PLANTS.get(exp["plant"], {})
    harvest_days = plant.get("harvest_days", 7)

    if day > harvest_days:
        await update.message.reply_text(
            f"🌾 Урожай уже готов, ждёт тебя {day - harvest_days} {'день' if day-harvest_days==1 else 'дня'}!\n\n"
            f"✂️ Срежь ножницами, промой и попробуй!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌾 Урожай собран", callback_data="harvest_done")
            ]])
        )
        return

    already = db.log_watering(user_id)
    if already:
        await update.message.reply_photo(
            photo=IMG_WATER,
            caption=f"✅ Уже поливал сегодня! День {day} из {plant.get('harvest_days',7)} 🌅",
            reply_markup=main_keyboard()
        )
    else:
        db.add_points(user_id, 5)
        await update.message.reply_photo(
            photo=IMG_WATER,
            caption=(
                f"💧 Полив записан! День {day}\n\n"
                f"Совет: 2–3 ст.ложки воды.\n"
                f"Субстрат влажный, но не мокрый!\n\n"
                f"⭐ +5 очков!"
            ),
            reply_markup=main_keyboard()
        )
        await check_achievements(update, user_id)

async def measure_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exp = db.get_experiment(update.effective_user.id)
    if not exp:
        await update.message.reply_text("Сначала начни эксперимент! /start 🌱", reply_markup=main_keyboard())
        return
    context.user_data["waiting_height"] = True
    await update.message.reply_photo(
        photo=IMG_SPROUTS,
        caption="📏 Измерь самый высокий росток линейкой\n\nНапиши высоту в мм (например: 15)"
    )

async def measure_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.strip().replace(",", "."))
        if not 0 <= height <= 300:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введи число от 0 до 300, например: 25")
        return
    user_id = update.effective_user.id
    context.user_data["waiting_height"] = False
    day = db.get_experiment_day(user_id)
    prev = db.get_last_height(user_id)
    db.log_height(user_id, height)
    db.add_points(user_id, 10)
    growth = f"\n📈 Прирост: +{height-prev:.1f} мм" if prev is not None else ""
    comments = ["Семена в темноте 🌰", "Первые ростки! 🌱", "Отличный старт ☀️", "Бурный рост! 💡", "Почти готово! 🥗"]
    await update.message.reply_text(
        f"✅ Записано! {height}мм{growth}\n"
        f"День {day}\n"
        f"{comments[min(int(height/15),4)]}\n\n"
        f"⭐ +10 очков!",
        reply_markup=main_keyboard()
    )
    await check_achievements(update, user_id)

async def diary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exp = db.get_experiment(user_id)
    if not exp:
        await update.message.reply_text("Начни эксперимент через /start 🌱", reply_markup=main_keyboard())
        return
    day = db.get_experiment_day(user_id)
    plant = PLANTS.get(exp["plant"], {})
    harvest = plant.get("harvest_days", 7)
    pct = min(int(day/harvest*100), 100)
    bar = "🟩" * (pct//10) + "⬜" * (10 - pct//10)
    heights = db.get_heights(user_id)
    h_info = f"\n📏 Последний замер: {heights[-1]['height']} мм" if heights else ""
    await update.message.reply_text(
        f"📒 Дневник исследователя\n{'─'*20}\n"
        f"{plant.get('emoji','🌱')} {exp['plant']} · День {day}/{harvest}{h_info}\n"
        f"💧 Поливов: {db.get_watering_count(user_id)} · ⭐ Очков: {db.get_points(user_id)}\n\n"
        f"{bar} {pct}%",
        reply_markup=diary_keyboard()
    )

async def diary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "chart":
        heights = db.get_heights(user_id)
        if not heights:
            await query.answer("Пока нет данных!", show_alert=True); return
        text = "📊 График роста\n\n"
        for r in heights[-7:]:
            text += f"День {r['day']:>2}: {'█'*min(int(r['height']/5),20)} {r['height']:.0f}мм\n"
        await query.edit_message_text(text, reply_markup=diary_keyboard())
    elif query.data == "note":
        context.user_data["adding_note"] = True
        await query.edit_message_text("📝 Напиши заметку в дневник")
    elif query.data == "history":
        entries = db.get_diary_entries(user_id)
        if not entries:
            await query.answer("Заметок пока нет!", show_alert=True); return
        text = "📖 История заметок\n\n" + "\n".join([f"День {e['day']}: {e['note']}" for e in entries[-5:]])
        await query.edit_message_text(text, reply_markup=diary_keyboard())

async def fact_of_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import random
    fact = random.choice(FACTS)
    await update.message.reply_photo(
        photo=IMG_SPROUTS,
        caption=f"🔬 Факт дня от Алема!\n\n{fact['title']}\n\n{fact['text']}\n\nЗапиши в STEM-дневник! 📒",
        reply_markup=main_keyboard()
    )
    try:
        speech_text = f"{fact['title']}. {fact['text']}"
        tts = gTTS(text=speech_text, lang='ru')
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        await update.message.reply_audio(
            audio=buf,
            filename="alem_fact.mp3",
            title="Факт дня от Алема",
            performer="BALA LAB"
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")

async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    earned = db.get_achievements(user_id)
    msg = f"🏆 Достижения исследователя\n⭐ Очков: {db.get_points(user_id)}\n{'─'*20}\n\n"
    for a in ACHIEVEMENTS:
        msg += f"{'✅' if a['id'] in earned else '🔒'} {a['name']}\n   {a['desc']}\n\n"
    await update.message.reply_text(msg, reply_markup=main_keyboard())

async def check_achievements(update: Update, user_id: int):
    earned = db.get_achievements(user_id)
    w = db.get_watering_count(user_id)
    h = db.get_heights(user_id)
    d = db.get_experiment_day(user_id)
    checks = [
        ("first_water", w>=1), ("first_measure", len(h)>=1),
        ("three_days", w>=3), ("week_done", d>=7),
        ("scientist", len(h)>=5 and w>=5)
    ]
    for aid, cond in checks:
        if aid not in earned and cond:
            db.grant_achievement(user_id, aid)
            db.add_points(user_id, 50)
            a = next((x for x in ACHIEVEMENTS if x["id"]==aid), None)
            if a:
                await update.message.reply_text(
                    f"🎉 Новое достижение!\n\n{a['name']}\n{a['desc']}\n\n+50 очков! ⭐"
                )

async def instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = STEPS[0]
    await update.message.reply_text(
        f"📋 Инструкция — шаг 1 из {len(STEPS)}\n\n{s['emoji']} {s['title']}\n\n{s['text']}\n\n💡 {s['tip']}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Следующий шаг ➡️", callback_data="step_1")]])
    )

async def step_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    n = int(query.data.replace("step_", ""))
    s = STEPS[n]
    btns = []
    if n < len(STEPS)-1: btns.append(InlineKeyboardButton("Следующий ➡️", callback_data=f"step_{n+1}"))
    if n > 0: btns.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"step_{n-1}"))
    await query.edit_message_text(
        f"📋 Шаг {n+1} из {len(STEPS)}\n\n{s['emoji']} {s['title']}\n\n{s['text']}\n\n💡 {s['tip']}",
        reply_markup=InlineKeyboardMarkup([btns]) if btns else None
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = db.get_experiment_day(update.effective_user.id)
    db.add_points(update.effective_user.id, 15)
    await update.message.reply_text(
        f"📸 Фото дня {day} сохранено!\nФотографируй каждый день — тайм-лапс! 🎬\n\n+15 очков! ⭐",
        reply_markup=main_keyboard()
    )

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    text = update.message.text
    exp = db.get_experiment(user_id)
    plant = exp["plant"] if exp else "не выбрано"
    day = db.get_experiment_day(user_id) if exp else 0
    ctx = f"Имя: {user_name}. Растение: {plant}. День: {day}. Поливов: {db.get_watering_count(user_id)}. Очков: {db.get_points(user_id)}."
    sys = SYSTEM_PROMPT.replace("{USER_CONTEXT}", ctx)
    history = context.user_data.get("ai_history", [])
    history.append({"role": "user", "content": text})
    await update.message.chat.send_action("typing")
    try:
        response = ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=sys,
            messages=history[-10:]
        )
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
        context.user_data["ai_history"] = history[-10:]
        db.add_points(user_id, 2)
        await update.message.reply_text(reply, reply_markup=main_keyboard())
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text("Упс, попробуй ещё раз! 😅", reply_markup=main_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Кнопки меню — всегда работают в первую очередь
    if "Полить" in text:
        context.user_data["waiting_height"] = False
        context.user_data["adding_note"] = False
        await water(update, context); return
    elif "Записать рост" in text:
        context.user_data["waiting_height"] = False
        context.user_data["adding_note"] = False
        await measure_start(update, context); return
    elif "дневник" in text.lower():
        context.user_data["waiting_height"] = False
        context.user_data["adding_note"] = False
        await diary(update, context); return
    elif "Факт" in text:
        context.user_data["waiting_height"] = False
        await fact_of_day(update, context); return
    elif "Достижени" in text:
        context.user_data["waiting_height"] = False
        await achievements(update, context); return
    elif "Инструкци" in text:
        context.user_data["waiting_height"] = False
        await instruction(update, context); return

    # Ввод высоты
    if context.user_data.get("waiting_height"):
        await measure_save(update, context); return

    # Ввод заметки
    if context.user_data.get("adding_note"):
        context.user_data["adding_note"] = False
        day = db.get_experiment_day(user_id)
        db.add_diary_entry(user_id, day, text)
        db.add_points(user_id, 5)
        await update.message.reply_text(f"✅ Заметка записана! +5 очков ⭐\n\n\"{text}\"", reply_markup=main_keyboard())
        return

    # Всё остальное → ИИ
    await ai_reply(update, context)

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    for u in db.get_active_users():
        if not db.watered_today(u["user_id"]):
            try:
                await context.bot.send_message(
                    u["user_id"],
                    f"☀️ Доброе утро, {u['name']}!\n"
                    f"🌱 День {db.get_experiment_day(u['user_id'])} эксперимента\n"
                    f"💧 Не забудь полить микрозелень!",
                    reply_markup=main_keyboard()
                )
            except: pass

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token: raise ValueError("Нет TELEGRAM_TOKEN")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key: raise ValueError("Нет ANTHROPIC_API_KEY")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_plant, pattern="^plant_"))
    app.add_handler(CallbackQueryHandler(cancel_cb, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(diary_callback, pattern="^(chart|note|history)$"))
    app.add_handler(CallbackQueryHandler(step_callback, pattern="^step_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_daily(send_daily_reminder, time=time(9, 0), name="reminder")
    logger.info("BALA LAB ИИ-бот запущен! 🌱✨")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
 
