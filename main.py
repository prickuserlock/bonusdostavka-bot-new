from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
from aiogram import Bot
import os
import subprocess
import threading

app = FastAPI()
templates = Jinja2Templates(directory="templates")

BOTS_DIR = "bots"
os.makedirs(BOTS_DIR, exist_ok=True)

BOT_CODE = '''import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import qrcode

bot = Bot("{token}")
dp = Dispatcher()

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, code TEXT)")

kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Мой баланс"), KeyboardButton(text="Виртуальная карта")]
], resize_keyboard=True)

def get_code(uid):
    cur.execute("SELECT code FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    if row and row[0]: return row[0]
    code = f"client_{uid}"
    cur.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))
    cur.execute("UPDATE users SET code=? WHERE id=?", (code, uid))
    conn.commit()
    return code

@dp.message_handler(CommandStart(deep_link=True))
@dp.message_handler(commands=["start"])
async def start(message: Message):
    await message.answer("BonusDostavkaBot — ваш бонусный бот готов!", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Виртуальная карта")
async def card(message: Message):
    code = get_code(message.from_user.id)
    username = (await bot.get_me()).username
    link = f"https://t.me/{username}?start={code}"
    qrcode.make(link).save("qr.png")
    with open("qr.png", "rb") as f:
        await message.answer_photo(f, caption="Ваша виртуальная карта")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
'''

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/create")
async def create(token: str = Form(...)):
    try:
        test_bot = Bot(token=token)
        me = await test_bot.get_me()
        bot_id = me.id
        username = me.username

        bot_dir = os.path.join(BOTS_DIR, f"bot_{bot_id}")
        os.makedirs(bot_dir, exist_ok=True)
        
        with open(os.path.join(bot_dir, "bot.py"), "w", encoding="utf-8") as f:
            f.write(BOT_CODE.format(token=token))

        def run_bot():
            subprocess.Popen(["python", "bot.py"], cwd=bot_dir)
        threading.Thread(target=run_bot, daemon=True).start()

        await test_bot.session.close()
        return templates.TemplateResponse("success.html", {
            "request": None,
            "username": username,
            "bot_link": f"https://t.me/{username}"
        })
    except Exception as e:

        return HTMLResponse(f"<h2>Ошибка: {e}</h2><a href='/'>Назад</a>", status_code=400)
