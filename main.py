import asyncio
import logging
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.dispatcher import filters
from aiogram.utils import executor
import vk_api
from vk_api.upload import VkUpload
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from aiogram.utils.markdown import escape_md

logging.basicConfig(level=logging.INFO)

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
    vk_token = Column(String, nullable=True)
    vk_target_id = Column(BigInteger, nullable=True)  # Собственный VK ID пользователя
    tg_target_username = Column(String, nullable=True)  # Username получателя в TG
    is_active = Column(Boolean, default=True)

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

    # Показываем только пользователей с привязанным VK
    users = session.query(User).filter(
        User.is_active == True,
        User.vk_target_id.isnot(None)
    ).all()

    if not users:
        await message.answer("⚠️ Нет доступных пользователей для отправки сообщений.")
        return

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for u in users:
        # Показываем только TG username
        keyboard.add(types.KeyboardButton(f"@{u.tg_username}"))

    await message.answer("👥 Выбери получателя:", reply_markup=keyboard)

@dp.message_handler(commands=["status"])
async def status_cmd(message: Message):
    username = message.from_user.username
    user = session.query(User).filter_by(tg_username=username).first()

    if not user:
        await message.reply("❌ Ты не зарегистрирован. Напиши /start для регистрации.")
        return
    
    recipient_info = "❌" if not user.tg_target_username else f"@{user.tg_target_username} (VK ID: {session.query(User.vk_target_id).filter_by(tg_username=user.tg_target_username).scalar() or '❌'})"

    info = (
        f"👤 Информация о тебе:\n"
        f"👥 Username: @{user.tg_username}\n"
        f"🆔 TG Chat ID: {user.tg_bot_chat_id or '❌'}\n"
        f"🔑 VK Token: {'✅' if user.vk_token else '❌'}\n"
        f"🎯 Получатель: {recipient_info}\n"
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

    # Обработка выбора получателя
    if message.text and message.text.startswith('@'):
        try:
            target_username = message.text[1:]  # Убираем @
            recipient = session.query(User).filter_by(tg_username=target_username).first()
            
            if recipient and recipient.vk_target_id:
                # Обновляем данные отправителя
                sender_user.tg_target_username = recipient.tg_username
                session.commit()
                
                await message.reply(
                    f"✅ Теперь сообщения будут отправляться пользователю "
                    f"@{recipient.tg_username} (VK ID: {recipient.vk_target_id})"
                )
                return
            else:
                await message.reply("⚠️ Пользователь не найден или у него не привязан VK")
                return
        except Exception as e:
            logging.warning(f"Ошибка обработки получателя: {e}")

    # Проверяем, что получатель выбран
    if not sender_user.tg_target_username:
        await message.reply("⚠️ Сначала выбери получателя через /start.")
        return

    # Находим VK ID получателя по его TG username
    recipient = session.query(User).filter_by(tg_username=sender_user.tg_target_username).first()
    if not recipient or not recipient.vk_target_id:
        await message.reply("❌ Ошибка: получатель не найден")
        return

    # Отправка сообщений
    try:
        vk = vk_api.VkApi(token=sender_user.vk_token)
        upload = VkUpload(vk)
        
        if message.content_type == "text":
            vk.get_api().messages.send(
                user_id=recipient.vk_target_id,  # VK ID получателя из его профиля
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
                await message.reply("⚠️ Ошибка при загрузке голосового")

    except Exception as e:
        logging.exception(e)
        await message.reply(f"❌ Ошибка при отправке в VK: {str(e)}")

async def poll_vk():
    last_ids = {}
    while True:
        try:
            users = session.query(User).filter(
                User.is_active == True,
                User.tg_target_username.isnot(None)
            ).all()

            for user in users:
                recipient = session.query(User).filter_by(tg_username=user.tg_target_username).first()
                if not recipient or not recipient.vk_target_id:
                    continue
                
                try:
                    vk = vk_api.VkApi(token=user.vk_token)
                    api = vk.get_api()
                    
                    # Получаем последние сообщения (2 последних чтобы избежать пропуска)
                    messages = api.messages.getHistory(
                        user_id=recipient.vk_target_id,
                        count=2,
                        rev=0  # В прямом порядке (от старых к новым)
                    ).get("items", [])
                    
                    if not messages:
                        continue
                    
                    # Берем последнее сообщение в диалоге
                    msg = messages[-1]
                    
                    # Пропускаем исходящие сообщения (которые отправили мы)
                    if msg["out"] == 1:
                        continue
                    
                    # Проверяем, что сообщение именно от нужного пользователя
                    if msg["from_id"] != recipient.vk_target_id:
                        continue
                    
                    # Проверка на дубликаты
                    if last_ids.get(user.id) == msg["id"]:
                        continue
                    
                    last_ids[user.id] = msg["id"]
                    
                    # Определяем имя отправителя
                    try:
                        sender_info = api.users.get(user_ids=msg["from_id"])
                        sender_name = f"{sender_info[0]['first_name']} {sender_info[0]['last_name']}"
                    except Exception:
                        sender_name = f"id{msg['from_id']}"
                    
                    attachments = msg.get("attachments", [])
                    media_sent = False
                    
                    # Обработка вложений
                    for att in attachments:
                        if att["type"] == "photo":
                            url = max(att["photo"]["sizes"], key=lambda x: x["width"])["url"]
                            await bot.send_photo(user.tg_bot_chat_id, photo=url, caption=f"📷 Фото от {sender_name}")
                            media_sent = True
                        
                        elif att["type"] == "audio_message":
                            url = att["audio_message"]["link_ogg"]
                            await bot.send_voice(user.tg_bot_chat_id, voice=url, caption=f"🎤 Голосовое от {sender_name}")
                            media_sent = True
                    
                    # Отправка текстового сообщения
                    if not media_sent and msg.get("text"):
                        await bot.send_message(
                            user.tg_bot_chat_id,
                            f"📩 Новое сообщение от {sender_name}:\n{msg['text']}"
                        )
                
                except Exception as e:
                    logging.exception(f"[VK polling error for user_id {user.id}]: {e}")
        
        except Exception as e:
            logging.exception(f"[General polling error]: {e}")
        
        await asyncio.sleep(3)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(poll_vk())
    executor.start_polling(dp, skip_updates=True)