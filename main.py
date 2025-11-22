from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3, qrcode, asyncio, logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import Update, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, run_app
import aiohttp

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Одна общая база для всех ботов
conn = sqlite3.connect("all_bots.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS bots (
    bot_id INTEGER PRIMARY KEY,
    token TEXT,
    username TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    bot_id INTEGER,
    user_id INTEGER,
    code TEXT,
    points INTEGER DEFAULT 0,
    PRIMARY KEY (bot_id, user_id)
)""")
conn.commit()

# Хранилище активных ботов
active_bots = {}

async def start_bot(token: str):
    bot = Bot(token=token)
    dp = Dispatcher()
    
    me = await bot.get_me()
    bot_id = me.id
    username = me.username
    
    # Сохраняем в базу
    cur.execute("INSERT OR REPLACE INTO bots (bot_id, token, username) VALUES (?,?,?)", 
                (bot_id, token, username))
    conn.commit()
    
    @dp.message(CommandStart())
    async def start(message: Message):
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="Виртуальная карта"), KeyboardButton(text="Мой баланс")]
        ], resize_keyboard=True)
        await message.answer("BonusDostavkaBot работает! Нажми кнопку", reply_markup=kb)
    
    @dp.message(F.text == "Виртуальная карта")
    async def card(message: Message):
        user_id = message.from_user.id
        cur.execute("SELECT code FROM users WHERE bot_id=? AND user_id=?", (bot_id, user_id))
        row = cur.fetchone()
        if row and row[0]:
            code = row[0]
        else:
            code = f"client_{user_id}"
            cur.execute("INSERT INTO users (bot_id, user_id, code) VALUES (?,?,?)", 
                       (bot_id, user_id, code))
            conn.commit()
        
        link = f"https://t.me/{username}?start={code}"
        qrcode.make(link).save(f"qr_{bot_id}_{user_id}.png")
        
        with open(f"qr_{bot_id}_{user_id}.png", "rb") as photo:
            await message.answer_photo(photo, caption=f"Твоя карта BonusDostavkaBot\nКод: {code}")
    
    @dp.message(F.text == "Мой баланс")
    async def balance(message: Message):
        cur.execute("SELECT points FROM users WHERE bot_id=? AND user_id=?", (bot_id, message.from_user.id))
        row = cur.fetchone()
        points = row[0] if row else 0
        await message.answer(f"У тебя {points} бонусов")
    
    active_bots[bot_id] = {"bot": bot, "dp": dp}
    asyncio.create_task(dp.start_polling(bot))
    logging.info(f"Бот @{username} запущен через polling в фоне")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/create")
async def create(token: str = Form(...), request: Request = None):
    try:
        bot = Bot(token=token)
        me = await bot.get_me()
        username = me.username
        
        # Запускаем бота
        asyncio.create_task(start_bot(token))
        
        await asyncio.sleep(2)  # даём время на запуск
        
        return templates.TemplateResponse("success.html", {
            "request": request,
            "username": username,
            "bot_link": f"https://t.me/{username}"
        })
    except Exception as e:
        return HTMLResponse(f"<h2 style='color:red;'>Ошибка: {str(e)}</h2><a href='/'>Назад</a>")
