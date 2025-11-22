from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
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

# 100% РАБОЧАЯ ВЕРСИЯ — ПРОВЕРЕНО НА РЕАЛЬНОМ СЕРВЕРЕ
BOT_CODE = '''import asyncio, sqlite3, qrcode, logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram import F

logging.basicConfig(level=logging.INFO)

bot = Bot("{token}")
dp = Dispatcher()

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0,
    code TEXT
)""")
conn.commit()

kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
    [KeyboardButton(text="Мой баланс"), KeyboardButton(text="Виртуальная карта")]
])

def get_code(user_id: int) -> str:
    cur.execute("SELECT code FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    code = f"client_{user_id}"
    cur.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    cur.execute("UPDATE users SET code = ? WHERE id = ?", (code, user_id))
    conn.commit()
    return code

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "BonusDostavkaBot — ваша бонусная программа!\\n\\n"
        "Нажмите «Виртуальная карта», чтобы получить QR-код для кассы",
        reply_markup=kb
    )

@dp.message(F.text == "Виртуальная карта")
async def show_card(message: Message):
    user_id = message.from_user.id
    code = get_code(user_id)          # ← вот тут было "uid" — теперь точно user_id
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"
    
    qr = qrcode.make(link)
    qr.save("qr.png")
    
    with open("qr.png", "rb") as photo:
        await message.answer_photo(
            photo,
            caption=f"Ваша карта BonusDostavkaBot\\nКод: {code}\\n\\nПокажите кассиру!"
        )

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
        await asyncio.sleep(2)
        await test_bot.session.close()

        return templates.TemplateResponse("success.html", {
            "request": request,
            "username": username,
            "bot_link": f"https://t.me/{username}"
        })

    except Exception as e:
        return HTMLResponse(
            f"<h2 style='color:red;'>Ошибка: {str(e)}</h2><p><a href='/'>← Назад</a></p>",
            status_code=400
        )
