import os
import asyncio
import sqlite3
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from fastapi import FastAPI, Request
import uvicorn


# ========================
# VARIAVEIS AMBIENTE
# ========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
INVICTUS_API_TOKEN = os.getenv("INVICTUS_API_TOKEN")
POSTBACK_URL = os.getenv("POSTBACK_URL")

CLIENT_NAME = os.getenv("CLIENT_NAME")
CLIENT_EMAIL = os.getenv("CLIENT_EMAIL")
CLIENT_PHONE = os.getenv("CLIENT_PHONE")
CLIENT_DOCUMENT = os.getenv("CLIENT_DOCUMENT")

PRODUCT_HASH = os.getenv("PRODUCT_HASH")
OFFER_HASH = os.getenv("OFFER_HASH")

GROUP_LINK = os.getenv("GROUP_LINK")

PRICE = int(os.getenv("PRICE_CENTS", "3790"))


# ========================
# BOT TELEGRAM
# ========================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()


# ========================
# DATABASE
# ========================

def db():
    return sqlite3.connect("database.db")


def init_db():

    conn = db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS tx(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        txid TEXT
    )
    """)

    conn.commit()
    conn.close()


# ========================
# GERAR PIX
# ========================

def create_pix(user_id):

    url = "https://api.invictuspay.app.br/api/public/v1/transactions"

    params = {
        "api_token": INVICTUS_API_TOKEN
    }

    payload = {

        "amount": PRICE,
        "offer_hash": OFFER_HASH,
        "payment_method": "pix",
        "installments": 1,
        "expire_in_days": 1,

        "customer": {

            "name": CLIENT_NAME,
            "email": CLIENT_EMAIL,
            "phone_number": CLIENT_PHONE,
            "document": CLIENT_DOCUMENT
        },

        "cart":[
            {
                "product_hash": PRODUCT_HASH,
                "title": "Acesso VIP",
                "price": PRICE,
                "quantity": 1,
                "operation_type": 1,
                "tangible": False
            }
        ]
    }

    r = requests.post(url, params=params, json=payload)

    data = r.json()

    print("INVICUTS RESPONSE:", data)

    if not data.get("success"):

        return "❌ Erro ao gerar pagamento. Tente novamente."

    pix = data.get("pix_copy_paste") or data.get("pix")

    txid = data.get("id")

    conn = db()

    conn.execute(
        "INSERT INTO tx(telegram_id,txid) VALUES(?,?)",
        (user_id,txid)
    )

    conn.commit()
    conn.close()

    return pix


# ========================
# BOTÕES
# ========================

def keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Comprar acesso",callback_data="pay")]
        ]
    )


# ========================
# COMANDO START
# ========================

@dp.message(CommandStart())
async def start(msg: types.Message):

    await msg.answer(

        "🔥 ACESSO VIP\n\n"
        "💰 Valor: R$37,90\n"
        "♾️ Acesso vitalício\n\n"
        "Clique abaixo para comprar",

        reply_markup=keyboard()
    )


# ========================
# GERAR PIX
# ========================

@dp.callback_query(lambda c:c.data=="pay")
async def pay(call: types.CallbackQuery):

    pix = create_pix(call.from_user.id)

    await call.message.answer(

        "💳 Segue o Pix Copia e Cola para pagamento:\n\n"
        f"`{pix}`",

        parse_mode="Markdown"
    )


# ========================
# WEBHOOK INVITCUS
# ========================

@app.post("/invictus/postback")
async def postback(req: Request):

    data = await req.json()

    status = data.get("status")
    txid = data.get("id")

    if status == "paid":

        conn = db()
        cur = conn.cursor()

        cur.execute(
            "SELECT telegram_id FROM tx WHERE txid=?",
            (txid,)
        )

        row = cur.fetchone()

        if row:

            user = row[0]

            await bot.send_message(
                user,
                "✅ Pagamento confirmado!"
            )

            await bot.send_message(
                user,
                f"🔓 Aqui está seu acesso:\n{GROUP_LINK}"
            )

    return {"ok": True}


# ========================
# INICIAR BOT
# ========================

async def start_bot():
    await dp.start_polling(bot)


async def main():

    init_db()

    asyncio.create_task(start_bot())

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT",8000))
    )

    server = uvicorn.Server(config)

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
