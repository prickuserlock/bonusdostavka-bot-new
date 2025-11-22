from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio, sqlite3, qrcode, logging, os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.basicConfig(level=logging.INFO)

# Одна база на всех
conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (bot_id INTEGER, user_id INTEGER, code TEXT, points INTEGER DEFAULT 0, PRIMARY KEY(bot_id, user_id))")
cur.execute("CREATE TABLE IF NOT EXISTS bots (bot_id INTEGER PRIMARY KEY, token TEXT, username TEXT)")
conn.commit()

active_bots = {}

async def run_bot(token: str):
    bot = Bot(token)
    dp = Dispatcher()

    try:
        me = await bot.get_me()
    except Exception as e:
        logging.error(f"Неверный токен: {e}")
        return

    bot_id = me.id
    username = me.username
    logging.info(f"Запущен бот @{username}")

    cur.execute("INSERT OR REPLACE INTO bots (bot_id, token, username) VALUES (?,?,?)", (bot_id, token, username))
    conn.commit()

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Виртуальная карта"), KeyboardButton(text="Мой баланс")]
    ], resize_keyboard=True)

    @dp.message(CommandStart())
    async def start(message: Message):
        await message.answer("BonusDostavkaBot готов!\nНажми «Виртуальная карта»", reply_markup=kb)

    @dp.message(F.text == "Виртуальная карта")
    async def card(message: Message):
        user_id = message.from_user.id
        cur.execute("SELECT code FROM users WHERE bot_id=? AND user_id=?", (bot_id, user_id))
        row = cur.fetchone()
        if row:
            code = row[0]
        else:
            code = f"client_{user_id}"
            cur.execute("INSERT INTO users (bot_id, user_id, code) VALUES (?,?,?)", (bot_id, user_id, code))
            conn.commit()

        link = f"https://t.me/{username}?start={code}"
        qr_path = f"qr_{bot_id}_{user_id}.png"
        qrcode.make(link).save(qr_path)

        # ВОТ ЭТО ГЛАВНОЕ ИСПРАВЛЕНИЕ:
        photo = FSInputFile(qr_path)
        await message.answer_photo(photo, caption=f"Твоя карта BonusDostavkaBot\nКод: {code}")

        os.remove(qr_path)  # чистим за собой

    @dp.message(F.text == "Мой баланс")
    async def balance(message: Message):
        cur.execute("SELECT points FROM users WHERE bot_id=? AND user_id=?", (bot_id, message.from_user.id))
        row = cur.fetchone()
        points = row[0] if row else 0
        await message.answer(f"У тебя {points} бонусов")

    active_bots[bot_id] = {"bot": bot, "dp": dp}
    asyncio.create_task(dp.start_polling(bot))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/create")
async def create(token: str = Form(...), request: Request = None):
    try:
        test_bot = Bot(token)
        me = await test_bot.get_me()
        await test_bot.session.close()

        asyncio.create_task(run_bot(token))

        return templates.TemplateResponse("success.html", {
            "request": request,
            "username": me.username,
            "bot_link": f"https://t.me/{me.username}"
        })

    except Exception as e:
        return HTMLResponse(f"<h2 style='color:red;'>Ошибка: {str(e)}<br>Проверь токен!</h2><a href='/'>Назад</a>")
