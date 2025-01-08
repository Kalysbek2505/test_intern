from telethon import TelegramClient
import asyncio
import re
from datetime import datetime, timedelta
import openai
import logging
import telethon
from decouple import config

openai.api_key = config('OPENAI_API_KEY')
ASSISTANT_ID = config('ASSISTANT_ID')
api_id = config('TELEGRAM_API_ID')
api_hash = config("TELEGRAM_API_HASH")
client = TelegramClient('session', api_id, api_hash)

privet = "Привет! Я ваш автоответчик."
spisok = ["слово", "привет где купить сигареты", "купить табак для кальяна на Самуи", "купить табак для кальяна на Бангкоке", "купить табак для кальяна на Паттайе"]
n = 1
m = 5
s = 30
coroutines = {}
sent_greetings = {}
answered_messages = {}
threads_cache = {}
thread_after = {}


import logging


logging.basicConfig(
    level=logging.INFO,  
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  
    handlers=[
        logging.StreamHandler()  
    ]
)

logger = logging.getLogger(__name__)


async def chat_with_openai(dialog_id: int, prompt: str) -> str:
    try:
        if dialog_id not in threads_cache:
            thread = openai.beta.threads.create()
            threads_cache[dialog_id] = thread.id

        openai.beta.threads.messages.create(
            thread_id=threads_cache[dialog_id],
            role="user",
            content=prompt
        )

        run = openai.beta.threads.runs.create(
            thread_id=threads_cache[dialog_id],
            assistant_id=ASSISTANT_ID
        )

        while True:
            run_status = openai.beta.threads.runs.retrieve(
                thread_id=threads_cache[dialog_id],
                run_id=run.id
            )
            if run_status.status in ["completed", "expired", "cancelled", "failed"]:
                break
            await asyncio.sleep(1)

        after = thread_after[threads_cache[dialog_id]] if threads_cache[dialog_id] in thread_after else None
        messages = openai.beta.threads.messages.list(thread_id=threads_cache[dialog_id], before=after)

        for msg in messages.data:
            if msg.role == "assistant":
                thread_after[threads_cache[dialog_id]] = msg.id
                return msg.content[0].text.value

        return "Ответ ассистента не найден."
    except Exception as e:
        return f"Ошибка: {str(e)}"

async def monitor():
    while True:
        try:
            dialogs = await client.get_dialogs(10)
            for d in dialogs:
                logging.info(f"Обработка диалога: {d.name}")
                if d.is_group or d.is_channel or d.pinned or d.entity.bot:
                    logging.info(f"Пропуск диалога: {d.name} - Это группа, канал или бот.")
                    continue
                msgs = await client.get_messages(d.id, 1)
                me = await client.get_me()
                if msgs and msgs[0].from_id != me.id:
                    if d.id not in coroutines:
                        coroutines[d.id] = asyncio.create_task(handler(d))
        except Exception as e:
            logging.error(f"Ошибка при обработке: {e}")
        await asyncio.sleep(60)

async def handler(dialog):
    try:
        me = await client.get_me()
        t = datetime.now()
        r = 0  # Счетчик ответов
        last_msg = await client.get_messages(dialog.id, 1)

        if dialog.id not in sent_greetings:
            if last_msg and last_msg[0].from_id != me.id:
                try:
                    await client.send_message(dialog.id, privet)
                    sent_greetings[dialog.id] = True
                    logging.info(f"Отправлено приветственное сообщение в диалог: {dialog.name}")
                except telethon.errors.rpcerrorlist.InputUserDeactivatedError:
                    logging.warning(f"Пользователь в диалоге {dialog.name} удален. Пропуск.")
                    return
                except Exception as e:
                    logging.error(f"Ошибка при отправке сообщения в диалог {dialog.name}: {e}")

        while True:
            await asyncio.sleep(n * 60)
            msgs = await client.get_messages(dialog.id, 50)
            for m in msgs:
                if m.from_id == me.id:
                    continue
                if m.id in answered_messages:
                    continue
                if any(re.search(w, m.message or "", re.IGNORECASE) for w in spisok):
                    logging.info(f"Получено сообщение: {m.message}")
                    try:
                        response = await chat_with_openai(dialog.id, m.message)
                        logging.info(f"Ответ модели: {response}")
                        await client.send_message(dialog.id, response)
                        answered_messages[m.id] = True
                        r += 1  
                    except Exception as e:
                        logging.error(f"Ошибка при обращении к OpenAI API: {e}")
            if r >= 3:  
                logging.info(f"Превышено количество ответов: {r}")
                break
            if datetime.now() - t > timedelta(minutes=s) or r >= 5:
                logging.info(f"Время ожидания истекло или достигнуто ограничение по количеству ответов.")
                break
    finally:
        coroutines.pop(dialog.id, None)


async def main():
    await client.start()
    await monitor()

with client:
    client.loop.run_until_complete(main())
