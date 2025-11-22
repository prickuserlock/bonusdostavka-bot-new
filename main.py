from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio, os, subprocess, threading
from aiogram import Bot

app = FastAPI()
templates = Jinja2Templates(directory="templates")
os.makedirs("bots", exist_ok=True)

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

        bot_dir = f"bots/bot_{bot_id}"
        os.makedirs(bot_dir, exist_ok=True)

        code = f"""import asyncio, sqlite3, qrcode
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram import F

bot = Bot("{token}")
dp = Dispatcher()

conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, code TEXT)")

kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="Виртуальная карта")]])

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("Нажмите кнопку ниже →", reply_markup=kb)

@dp.message(F.text == "Виртуальная карта")
async def card(m: Message):
    cur.execute("SELECT code FROM users WHERE id=?", (m.from_user.id,))
    row = cur.fetchone()
    if not row or not row[0]:
        code = f"client_{m.from_user.id}"
        cur.execute("INSERT OR IGNORE INTO users (id,code) VALUES (?,?)", (m.from_user.id, code))
        conn.commit()
    else:
        code = row[0]
    link = f"https://t.me/{(await bot.get_me()).username}?start={code}"
    qrcode.make(link).save("qr.png")
    await m.answer_photo(open("qr.png","rb"), caption=f"Ваша карта\\nКод: {code}")

asyncio.run(dp.start_polling(bot))"""

        with open(f"{bot_dir}/bot.py", "w", encoding="utf-8") as f:
            f.write(code)

        threading.Thread(target=lambda: subprocess.Popen(["python", "bot.py"], cwd=bot_dir), daemon=True).start()
        await asyncio.sleep(1)
        await test_bot.session.close()

        return templates.TemplateResponse("success.html", {"request":request, "username":username, "bot_link":f"https://t.me/{username}"})

    except Exception as e:
        return HTMLResponse(f"<h2 style='color:red;'>Ошибка: {e}</h2><a href='/'>Назад</a>")
