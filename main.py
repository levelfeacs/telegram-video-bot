import logging
import asyncio
import re
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from pyrogram import Client
from pyrogram.enums import ParseMode
from download_manager import download_and_send_video, download_playlist
import config
import yt_dlp

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Инициализация бота и Pyrogram-клиента
bot = Bot(config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
user_client = Client("my_session", api_id=config.API_ID, api_hash=config.API_HASH)

async def get_user_status(user_id):
    """
    Функция для проверки Premium-статуса пользователя.
    Здесь должна быть логика из вашей базы данных. Пока что это заглушка.
    """
    # Предположим, что у пользователя с ID 123456789 есть Premium
    return user_id == 123456789

@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    """
    Обрабатывает команду /start и отправляет приветственное сообщение с кнопками.
    """
    await message.answer(
        "👋 Привет! Я твой личный бот для скачивания видео.\n\n"
        "Просто отправь мне ссылку на видео, и я найду все доступные форматы.\n"
        "Или используй наше удобное веб-приложение!",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⚡️ Открыть Web App", web_app=types.WebAppInfo(url=config.WEB_APP_URL))],
                [types.InlineKeyboardButton(text="💎 Premium-подписка", callback_data="show_premium_info")]
            ]
        )
    )

@dp.callback_query(F.data == "show_premium_info")
async def show_premium_info_handler(callback: types.CallbackQuery):
    """
    Показывает информацию о Premium-подписке.
    """
    await callback.message.edit_text(
        "💎 **Premium-подписка**\n\n"
        "С Premium вы получаете:\n"
        "• Неограниченное количество скачиваний.\n"
        "• Загрузку файлов до 4 ГБ.\n"
        "• Скачивание плейлистов.\n"
        "• Отсутствие рекламы.\n\n"
        "Стоимость: **150 Stars** (для новых пользователей **100 Stars**).",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Купить Premium", callback_data="buy_premium")]
            ]
        )
    )
    await callback.answer()

@dp.callback_query(F.data == "buy_premium")
async def buy_premium_handler(callback: types.CallbackQuery):
    """
    Обрабатывает покупку Premium-подписки (заглушка).
    """
    await callback.message.edit_text("🛒 Пока что покупка недоступна. Пожалуйста, попробуйте позже.", parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.message(F.text.regexp(r"https?://\S+"))
async def handle_url(message: types.Message):
    """
    Обрабатывает сообщения, содержащие URL.
    """
    url = message.text
    is_premium = await get_user_status(message.from_user.id)

    # Проверка, является ли ссылка на плейлист
    if 'playlist' in url and is_premium:
        await message.answer(
            f"⚠️ Обнаружен плейлист. Хотите скачать его полностью?",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="Да, скачать весь плейлист", callback_data=f"download_playlist:{url}")],
                    [types.InlineKeyboardButton(text="Нет, только одно видео", callback_data=f"show_options:{url}")]
                ]
            )
        )
        return
    
    await show_options(message.chat.id, url, is_premium)

async def show_options(chat_id, url, is_premium):
    """
    Функция для отображения кнопок с форматами.
    """
    try:
        await bot.send_message(chat_id, "🔍 Ищу доступные форматы...")
        
        ydl_opts = {
            'listformats': True,
            'force_generic_extractor': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            formats = info_dict.get('formats', [])
            
            video_buttons = []
            audio_buttons = []
            
            # Фильтруем форматы
            for f in formats:
                if 'none' not in f['vcodec'] and f.get('ext') == 'mp4' and f.get('format_note'):
                    video_buttons.append(
                        types.InlineKeyboardButton(
                            text=f"{f['format_note']} ({f.get('filesize', 0) / 1024 / 1024:.1f} MB)",
                            callback_data=f"download:{url}:{f['format_id']}"
                        )
                    )
                elif 'none' not in f['acodec'] and f.get('ext') == 'mp3':
                    audio_buttons.append(
                        types.InlineKeyboardButton(
                            text=f"MP3 ({f.get('filesize', 0) / 1024 / 1024:.1f} MB)",
                            callback_data=f"download:{url}:{f['format_id']}"
                        )
                    )

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="🎥 Видео", callback_data="video_placeholder")],
                    [btn for btn in video_buttons],
                    [types.InlineKeyboardButton(text="🎵 Аудио", callback_data="audio_placeholder")],
                    [btn for btn in audio_buttons],
                ]
            )
            
            await bot.send_message(chat_id, "✅ Готово! Выберите нужный формат:", reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Ошибка при получении форматов: {e}")
        await bot.send_message(chat_id, "Извините, не удалось найти форматы для этого видео.")

@dp.callback_query(F.data.startswith("download_playlist:"))
async def handle_playlist_download_callback(callback: types.CallbackQuery):
    """
    Обрабатывает запрос на скачивание плейлиста.
    """
    url = callback.data.split(":")[1]
    is_premium = await get_user_status(callback.from_user.id)
    await download_playlist(user_client, callback.message, url, is_premium)
    await callback.answer("Начинаю загрузку плейлиста...", show_alert=True)

@dp.callback_query(F.data.startswith("download:"))
async def handle_download_callback(callback: types.CallbackQuery):
    """
    Обрабатывает нажатие на кнопку "Скачать".
    """
    parts = callback.data.split(":")
    url = parts[1]
    format_id = parts[2]
    
    is_premium = await get_user_status(callback.from_user.id)
    await download_and_send_video(user_client, callback.message, url, format_id, is_premium)
    await callback.answer("Начинаю загрузку...", show_alert=True)

@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    """
    Обрабатывает данные, полученные из Web App.
    """
    data = message.web_app_data.data
    try:
        json_data = json.loads(data)
        url = json_data.get('url')
        format_id = json_data.get('format_id')
        
        if url and format_id:
            is_premium = await get_user_status(message.from_user.id)
            await download_and_send_video(user_client, message, url, format_id, is_premium)
        else:
            await message.answer("Неверные данные из Web App.")
    except json.JSONDecodeError:
        await message.answer("Ошибка при обработке данных из Web App.")

async def main() -> None:
    logging.info("Starting Pyrogram client...")
    await user_client.start()
    logging.info("Pyrogram client started successfully.")
    
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
