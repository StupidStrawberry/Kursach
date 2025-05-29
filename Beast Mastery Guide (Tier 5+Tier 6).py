import asyncio
import logging
import time
import os
import secrets
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.dispatcher import filters
from aiogram.utils import executor
import vk_api
from vk_api.upload import VkUpload
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean, DateTime, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from fastapi import FastAPI, Request, HTTPException, Depends, status, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("APP_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TELEGRAM_BOT_TOKEN = "7886483462:AAH1uGjbnE3_EpwjTWHwSh58J03QXnEedPw"
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

engine = create_engine("postgresql://postgres:1532@localhost:5432/kursach")
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tg_username = Column(String, nullable=False)
    tg_bot_chat_id = Column(BigInteger)
    tg_api_id = Column(String)
    tg_api_hash = Column(String)
    tg_phone = Column(String)
    vk_token_encrypted = Column(LargeBinary)
    vk_token_nonce = Column(LargeBinary)
    vk_token_tag = Column(LargeBinary)
    vk_target_id = Column(BigInteger)
    email = Column(String)
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)


def encrypt_aes_256_gcm(text: str, key: bytes = None, iv: bytes = None) -> tuple:
    data = text.encode('utf-8')
    if key is None:
        key = os.urandom(32)
    if iv is None:
        iv = os.urandom(12)
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return ciphertext, key, iv, encryptor.tag

def decrypt_aes_256_gcm(ciphertext: bytes, key: bytes, iv: bytes, tag: bytes) -> str:
    decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
    return decrypted_data.decode('utf-8')


class CryptoService:
    def __init__(self):
        self.master_key = SECRET_KEY.encode()[:32]
    
    def encrypt(self, text: str) -> dict:
        ciphertext, key, iv, tag = encrypt_aes_256_gcm(text, self.master_key)
        return {
            'ciphertext': ciphertext,
            'nonce': iv,
            'tag': tag
        }
    
    def decrypt(self, encrypted_data: dict) -> str:
        return decrypt_aes_256_gcm(
            encrypted_data['ciphertext'],
            self.master_key,
            encrypted_data['nonce'],
            encrypted_data['tag']
        )

crypto_service = CryptoService()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Необходима авторизация",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = session.query(User).filter_by(tg_username=username).first()
    if user is None:
        raise credentials_exception
    return user


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = session.query(User).filter_by(tg_username=form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.tg_username}, expires_delta=access_token_expires
    )
    
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    response.set_cookie(key="username", value=user.tg_username)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/profile", response_class=HTMLResponse)
async def read_profile(request: Request, current_user: User = Depends(get_current_user)):
    vk_token = ""
    if current_user.vk_token_encrypted:
        try:
            vk_token = crypto_service.decrypt({
                'ciphertext': current_user.vk_token_encrypted,
                'nonce': current_user.vk_token_nonce,
                'tag': current_user.vk_token_tag
            })
        except Exception as e:
            logger.error(f"Ошибка дешифровки токена: {e}")
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "vk_token": vk_token
    })

@app.post("/api/settings")
async def update_settings(
    settings: dict,
    current_user: User = Depends(get_current_user)
):
    try:
        if 'tg_username' in settings:
            current_user.tg_username = settings['tg_username']
        if 'tg_api_id' in settings:
            current_user.tg_api_id = settings['tg_api_id']
        if 'tg_api_hash' in settings:
            encrypted = crypto_service.encrypt(settings['tg_api_hash'])
            current_user.tg_api_hash = encrypted['ciphertext']
        if 'tg_phone' in settings:
            current_user.tg_phone = settings['tg_phone']
        
        if 'vk_id' in settings:
            current_user.vk_target_id = settings['vk_id']
        if 'vk_token' in settings:
            encrypted = crypto_service.encrypt(settings['vk_token'])
            current_user.vk_token_encrypted = encrypted['ciphertext']
            current_user.vk_token_nonce = encrypted['nonce']
            current_user.vk_token_tag = encrypted['tag']
        
        session.commit()
        return {"status": "success"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


current_recipient = {}

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    chat_id = message.chat.id
    username = message.from_user.username

    if not username:
        await message.answer("⚠️ У тебя нет username в Telegram. Установи его в настройках и попробуй снова.")
        return

    user = session.query(User).filter_by(tg_username=username).first()

    if user:
        if not user.tg_bot_chat_id:
            user.tg_bot_chat_id = chat_id
            session.commit()
        await message.answer(f"✅ Привет, @{username}! Ты уже в системе.")
    else:
        new_user = User(
            tg_username=username,
            tg_bot_chat_id=chat_id,
            is_active=True
        )
        session.add(new_user)
        session.commit()
        await message.answer(f"👋 Привет, @{username}! Ты зарегистрирован.")

    users = session.query(User).filter(User.is_active == True, User.vk_target_id.isnot(None)).all()

    if not users:
        await message.answer("⚠️ Нет доступных пользователей для отправки сообщений.")
        return

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for u in users:
        if u.vk_target_id:
            label = f"{u.tg_target_username or 'пользователь'} ({u.vk_target_id})"
            keyboard.add(types.KeyboardButton(label))

    await message.answer("К какому VK-пользователю отправлять сообщения?", reply_markup=keyboard)

@dp.message_handler(commands=["status"])
async def status_cmd(message: Message):
    username = message.from_user.username
    user = session.query(User).filter_by(tg_username=username).first()

    if not user:
        await message.reply("❌ Ты не зарегистрирован. Напиши /start для регистрации.")
        return

    info = (
        f"👤 Информация о тебе:\n"
        f"👥 Username: @{user.tg_username}\n"
        f"🆔 TG Chat ID: {user.tg_bot_chat_id or '❌'}\n"
        f"🎯 VK Target ID: {user.vk_target_id or '❌'}\n"
        f"VK Token: {'✅' if user.vk_token else '❌'}\n"
        f"👤 Получатель TG: @{user.tg_target_username or '❌'}\n"
        f"Статус: {'🟢 Активен' if user.is_active else '🔴 Неактивен'}"
    )

    await message.reply(info)

@dp.message_handler(commands=["reset"])
async def reset_cmd(message: Message):
    sender_id = message.chat.id
    if sender_id in current_recipient:
        del current_recipient[sender_id]
        await message.reply("✅ Получатель сброшен. Выбери нового через /start.")
    else:
        await message.reply("⚠️ Нет активного получателя.")

@dp.message_handler(content_types=["text", "photo", "voice"])
async def handle_message(message: Message):
    sender_id = message.chat.id
    sender_username = message.from_user.username
    sender_user = session.query(User).filter_by(tg_username=sender_username).first()

    if not sender_user:
        await message.reply("❌ Вы не зарегистрированы в системе.")
        return

    if message.text and '(' in message.text and ')' in message.text:
        try:
            vk_id = int(message.text.split('(')[-1].split(')')[0])
            recipient = session.query(User).filter_by(vk_target_id=vk_id).first()
            if recipient:
                current_recipient[sender_id] = recipient
                await message.reply(f"Теперь сообщения будут отправляться пользователю @{recipient.tg_target_username or recipient.tg_username}")
                return
        except Exception as e:
            logging.warning(f"Ошибка обработки ID: {e}")

    if sender_id not in current_recipient:
        await message.reply("Сначала выбери получателя через /start.")
        return

    recipient = current_recipient[sender_id]
    vk = vk_api.VkApi(token=sender_user.vk_token)
    upload = VkUpload(vk)

    try:
        if message.content_type == "text":
            vk.get_api().messages.send(
                user_id=recipient.vk_target_id,
                message=message.text,
                random_id=int(time.time())
            )
            await message.reply("✅ Отправлено во ВКонтакте!")

        elif message.content_type == "photo":
            photo = message.photo[-1]
            await photo.download(destination_file := f"temp_{photo.file_id}.jpg")
            uploaded = upload.photo_messages(destination_file)[0]
            attachment = f"photo{uploaded['owner_id']}_{uploaded['id']}"
            vk.get_api().messages.send(
                user_id=recipient.vk_target_id,
                attachment=attachment,
                random_id=int(time.time())
            )
            await message.reply("📷 Фото отправлено во VK!")

        elif message.content_type == "voice":
            voice = await bot.download_file_by_id(message.voice.file_id)
            with open("temp_voice.ogg", "wb") as f:
                f.write(voice.getvalue())
            uploaded = upload.audio_message("temp_voice.ogg")
            if 'audio_message' in uploaded:
                am = uploaded['audio_message']
                attachment = f"audio_message{am['owner_id']}_{am['id']}"
                vk.get_api().messages.send(
                    user_id=recipient.vk_target_id,
                    attachment=attachment,
                    random_id=int(time.time())
                )
                await message.reply("🎤 Голосовое сообщение отправлено во VK!")
            else:
                await message.reply("⚠️ Ошибка при загрузке голосового: ответ VK не содержит audio_message")

    except Exception as e:
        logging.exception(e)
        await message.reply("❌ Ошибка при отправке в VK")

async def poll_vk():
    last_ids = {}

    while True:
        users = session.query(User).filter(User.is_active == True).all()

        for user in users:
            if not user.vk_token or not user.tg_bot_chat_id or not user.vk_target_id:
                continue

            try:
                vk = vk_api.VkApi(token=user.vk_token)
                api = vk.get_api()
                messages = api.messages.getHistory(user_id=user.vk_target_id, count=1).get("items", [])

                if not messages:
                    continue

                msg = messages[0]
                if msg["out"] or msg["from_id"] != user.vk_target_id:
                    continue

                if last_ids.get(user.id) == msg["id"]:
                    continue

                last_ids[user.id] = msg["id"]

                try:
                    sender_info = api.users.get(user_ids=msg["from_id"])
                    sender_name = f"{sender_info[0]['first_name']} {sender_info[0]['last_name']}"
                except Exception:
                    sender_name = f"id{msg['from_id']}"

                attachments = msg.get("attachments", [])
                media_sent = False

                for att in attachments:
                    if att["type"] == "photo":
                        url = max(att["photo"]["sizes"], key=lambda x: x["width"])["url"]
                        await bot.send_photo(user.tg_bot_chat_id, photo=url, caption=f"📷 Фото от {sender_name}")
                        media_sent = True

                    elif att["type"] == "audio_message":
                        url = att["audio_message"]["link_ogg"]
                        await bot.send_voice(user.tg_bot_chat_id, voice=url, caption=f"🎤 Голосовое от {sender_name}")
                        media_sent = True

                if not media_sent:
                    await bot.send_message(
                        user.tg_bot_chat_id,
                        f"📩 Новое сообщение от {sender_name}:\n{msg['text']}"
                    )

            except Exception as e:
                logging.exception(f"[VK polling error for user_id {user.id}]: {e}")

        await asyncio.sleep(5)


async def start_bot():
    loop = asyncio.get_event_loop()
    loop.create_task(poll_vk())
    await dp.start_polling()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
