from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio, os, subprocess, threading

app = FastAPI()
templates = Jinja2Templates(directory="templates")
os.makedirs("bots", exist_ok=True, mode=0o777)

# 100% РАБОЧИЙ ШАБЛОН БОТА (работает на Render)
BOT_CODE = """import asyncio, sqlite3, qrcode, logging, time
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

logging.basicConfig(level=logging.INFO)
logging.info("Бот начинает запуск...")

bot = Bot("{token}")
dp = Dispatcher()

# База данных
conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, code TEXT, points INTEGER DEFAULT 0)")

# Клавиатура
kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Виртуальная карта"), KeyboardButton(text="Мой баланс")]
], resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("BonusDostavkaBot запущен!\\n\\nНажми «Виртуальная карта»", reply_markup=kb)

@dp.message(F.text == "Виртуальная карта")
async def send_card(message: Message):
    user_id = message.from_user.id
    cur.execute("SELECT code FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if row and row[0]:
        code = row[0]
    else:
        code = f"client_{user_id}"
        cur.execute("INSERT INTO users (id, code) VALUES (?, ?)", (user_id, code))
        conn.commit()
    
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"
    qrcode.make(link).save("qr.png")
    
    with open("qr.png", "rb") as photo:
        await message.answer_photo(photo, caption=f"Твоя бонусная карта\\nКод: {code}")

@dp.message(F.text == "Мой баланс")
async def balance(message: Message):
    cur.execute("SELECT points FROM users WHERE id=?", (message.from_user.id,))
    row = cur.fetchone()
    points = row[0] if row else 0
    await message.answer(f"У тебя {points} бонусов")

async def main():
    logging.info("Бот полностью запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
"""

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/create")
async def create(token: str = Form(...), request: Request = None):
    try:
        from aiogram import Bot as TestBot
        test_bot = TestBot(token=token)
        me = await test_bot.get_me()
        username = me.username
        bot_id = me.id

        bot_dir = f"bots/bot_{bot_id}"
        os.makedirs(bot_dir, exist_ok=True)

        # Записываем код бота
        with open(f"{bot_dir}/bot.py", "w", encoding="utf-8") as f:
            f.write(BOT_CODE.replace("{token}", token))

        # Запускаем бота в отдельном потоке
        def run():
            subprocess.Popen(["python", "bot.py"], cwd=bot_dir)

        threading.Thread(target=run, daemon=True).start()
        await asyncio.sleep(6)  # даём боту 6 секунд на полный запуск

        await test_bot.session.close()

        return templates.TemplateResponse("success.html", {
            "request": request,
            "username": username,
            "bot_link": f"https://t.me/{username}"
        })

    except Exception as e:
        return HTMLResponse(f"<h2 style='color:red;'>Ошибка: {str(e)}</h2><a href='/'>← Назад</a>")
