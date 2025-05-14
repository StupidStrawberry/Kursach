import asyncio
import time
from telethon import TelegramClient, events
import vk_api
import threading
from functools import partial

# Конфигурация
TG_API_ID = 25432741
TG_API_HASH = 'f589d68777cd73bd3776a7505c226f76'
TG_PHONE = '+79504102514'
TG_TARGET_USERNAME = 'TolyaHuligan'
VK_TOKEN = 'vk1.a.zmXpRGrYfKpBeAFp6lW5hG-OFgMMBXPsOQ8BS-0x-NPyM9jqJ6B-l9xb9hIFpbB7Lxxbi6ru8xW6vmJZIuOaJTyT7gdqlY9s7j30CUDY1h-FfLZyD2WV_8rCKO1pyTYv6yfsZ_NKFmMs61K8t4sfgNypLYorZ17NRJ68VpQCCHAt-TlWYX-mvE5ka2uNOvq1yubwI24XxiwuP38Uxetgzg'
VK_TARGET_ID = 469968043

class Bridge:
    def __init__(self):
        self.tg_client = TelegramClient('tg_session', TG_API_ID, TG_API_HASH)
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.vk = self.vk_session.get_api()
        self.last_vk_msg_id = None
        self.loop = asyncio.new_event_loop()
        self.stop_event = threading.Event()

    async def tg_to_vk(self, event):
        if not event.is_private or not event.out:
            return
            
        chat = await event.get_chat()
        if hasattr(chat, 'username') and chat.username.lower() == TG_TARGET_USERNAME.lower():
            message = event.message.message
            print(f"Сообщение из Telegram: '{message}'")
            if message.strip():
                try:
                    self.vk.messages.send(
                        user_id=VK_TARGET_ID, 
                        message=message, 
                        random_id=int(time.time())
                    )
                    print(f"Сообщение отправлено в VK: {message}")
                except Exception as e:
                    print(f"Ошибка отправки в VK: {e}")

    def vk_polling(self):
        while not self.stop_event.is_set():
            try:
                messages = self.vk.messages.getHistory(user_id=VK_TARGET_ID, count=1)
                if messages.get('items'):
                    msg = messages['items'][0]
                    if not msg['out'] and msg['id'] != self.last_vk_msg_id:
                        self.last_vk_msg_id = msg['id']
                        text = msg['text']
                        print(f"[VK → Telegram]: {text}")
                        
                        # Безопасная отправка в Telegram из другого потока
                        asyncio.run_coroutine_threadsafe(
                            self.send_to_telegram(text),
                            self.loop
                        )
            except Exception as e:
                print(f"Ошибка VK polling: {e}")
            time.sleep(3)

    async def send_to_telegram(self, text):
        try:
            await self.tg_client.send_message(TG_TARGET_USERNAME, text)
            print(f"Сообщение отправлено в Telegram: {text}")
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")

    async def start(self):
        await self.tg_client.start(phone=TG_PHONE)
        self.tg_client.add_event_handler(
            self.tg_to_vk,
            events.NewMessage()
        )
        print("Мост запущен. Ctrl+C для остановки.")

    def run(self):
        # Запускаем event loop в основном потоке
        asyncio.set_event_loop(self.loop)
        
        # Запускаем Telegram клиент
        self.loop.run_until_complete(self.start())
        
        # Запускаем VK polling в отдельном потоке
        vk_thread = threading.Thread(target=self.vk_polling, daemon=True)
        vk_thread.start()
        
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            print("Остановка моста...")
        finally:
            self.stop_event.set()
            self.loop.run_until_complete(self.tg_client.disconnect())
            self.loop.close()

if __name__ == "__main__":
    bridge = Bridge()
    bridge.run()
