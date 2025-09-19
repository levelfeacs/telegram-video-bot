import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from pyrogram import Client, errors
from pyrogram.enums import ParseMode
import yt_dlp
import os
import asyncio

# Настройка
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# API-ключи для Pyrogram (для Premium-аккаунта)
# Замените на свои, когда получите аккаунт
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Pyrogram Client (для 4 ГБ лимита)
# Пока закомментирован. Раскомментируйте, когда получите аккаунт и API-ключи
# user_client = Client("my_account", api_id=API_ID, api_hash=API_HASH)
# user_client.start()

# Функция для отправки файла с проверкой на 4 ГБ
async def send_video_from_url(url, message, is_premium=False):
    """
    Скачивает и отправляет видео, учитывая лимиты
    """
    await message.answer("Начинаю загрузку. Это может занять время...")

    try:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': '%(title)s.%(ext)s'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            filesize = info_dict.get('filesize', 0)

            # Проверка размера файла
            if filesize > (4 * 1024 * 1024 * 1024) and is_premium:
                await message.answer("Размер файла превышает лимит в 4 ГБ даже для Premium-аккаунта.")
                return
            elif filesize > (2 * 1024 * 1024 * 1024) and not is_premium:
                await message.answer(
                    "Видео слишком большое для бесплатного аккаунта (лимит 2 ГБ).\n"
                    "Чтобы скачивать большие видео (до 4 ГБ), "
                    "нужен Telegram Premium.\n"
                    "Просто попробуйте отправить ссылку еще раз, когда у вас будет Premium."
                )
                return

            # Скачивание файла
            ydl.download([url])

            video_title = info_dict.get('title')
            filename = ydl.prepare_filename(info_dict)

            # Отправка файла
            await message.answer_video(
                video=types.FSInputFile(filename),
                caption=f"Вот ваше видео: **{video_title}**"
            )

            os.remove(filename)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("Извините, произошла ошибка. Убедитесь, что ссылка правильная.")

# Обработчики команд и сообщений
@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    await message.answer(
        "Привет! Отправь мне ссылку на видео, и я его скачаю. "
        "Также ты можешь использовать наше веб-приложение.",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Open Web App", web_app=types.WebAppInfo(url="https://your-domain.com"))]
            ],
            resize_keyboard=True
        )
    )

@dp.message(F.text.regexp(r"https?://\S+"))
async def handle_url(message: types.Message):
    # Пока используем только Bot API
    is_premium_user = False
    await send_video_from_url(message.text, message, is_premium_user)

async def main() -> None:
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())
