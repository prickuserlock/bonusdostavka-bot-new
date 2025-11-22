from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import asyncio, os, sqlite3, qrcode
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Update
from aiogram.webhook import SimpleWebhook
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Хранилище ботов
bots = {}

# База для админки (пока простая)
admin_db = sqlite3.connect("admin.db")
admin_cur = admin_db.cursor()
admin_cur.execute("CREATE TABLE IF NOT EXISTS clients (bot_id INTEGER PRIMARY KEY, username TEXT, token TEXT, paid_until TEXT)")
admin_db.commit()

BOT_CODE = """
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import sqlite3, qrcode, asyncio

bot = Bot("{token}")
dp = Dispatcher()

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, code TEXT, points INTEGER DEFAULT 0)")

kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Виртуальная карта"), KeyboardButton(text="Мой баланс")]
], resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("BonusDostavkaBot работает!\\nНажми кнопку ниже", reply_markup=kb)

@dp.message(F.text == "Виртуальная карта")
async def card(message: Message):
    uid = message.from_user.id
    cur.execute("SELECT code FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    if row and row[0]:
        code = row[0]
    else:
        code = f"client_{uid}"
        cur.execute("INSERT INTO users (id, code) VALUES (?, ?)", (uid, code))
        conn.commit()
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"
    qrcode.make(link).save("qr.png")
    await message.answer_photo(open("qr.png", "rb"), caption=f"Твоя карта\\nКод: {code}")

@dp.message(F.text == "Мой баланс")
async def balance(message: Message):
    cur.execute("SELECT points FROM users WHERE id=?", (message.from_user.id,))
    row = cur.fetchone()
    points = row[0] if row else 0
    await message.answer(f"У тебя {points} бонусов")

async def run():
    await dp.start_polling(bot)
"""

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/create")
async def create(token: str = Form(...), request: Request = None):
    try:
        test_bot = Bot(token=token)
        me = await test_bot.get_me()
        username = me.username
        bot_id = me.id

        # Сохраняем в админку
        admin_cur.execute("INSERT OR REPLACE INTO clients (bot_id, username, token) VALUES (?,?,?)", (bot_id, usernames, token))
        admin_db.commit()

        # Создаём и запускаем бота
        bot = Bot(token=token)
        dp = Dispatcher()
        exec(BOT_CODE.format(token=token), {}, {"dp": dp, "bot": bot, "types": types, "CommandStart": CommandStart, "F": F, "Message": Message, "ReplyKeyboardMarkup": ReplyKeyboardMarkup, "KeyboardButton": KeyboardButton})
        
        # Запускаем в фоне
        async def run_bot():
            await dp.start_polling(bot)
        asyncio.create_task(run_bot())
        
        bots[bot_id] = {"bot": bot, "dp": dp}

        return templates.TemplateResponse("success.html", {
            "request": request,
            "username": username,
            "bot_link": f"https://t.me/{username}"
        })

    except Exception as e:
        return HTMLResponse(f"<h2 style='color:red;'>Ошибка: {str(e)}</h2><a href='/'>Назад</a>")

# Вебхук для всех ботов
@app.post("/webhook/{bot_id}")
async def webhook(bot_id: int, update: dict):
    if bot_id in bots:
        await bots[bot_id]["dp"].feed_update(bots[bot_id]["bot"], Update(**update))
    return JSONResponse({"ok": True})
