import yt_dlp
import os
import logging
from pyrogram import Client, errors
from pyrogram.enums import ParseMode
from aiogram.types import FSInputFile, InputFile
import asyncio
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Словарь для отслеживания прогресса загрузки
DOWNLOAD_PROGRESS = {}

# Хук для yt-dlp, который будет обновлять прогресс
def progress_hook(d):
    """
    Обновляет словарь DOWNLOAD_PROGRESS.
    """
    if d['status'] == 'downloading':
        file_id = d['info_dict']['id']
        percent_str = d.get('_percent_str', '0%').strip()
        DOWNLOAD_PROGRESS[file_id] = percent_str

async def send_download_progress(message, file_id, total_videos, current_video_num):
    """
    Отправляет сообщение с прогрессом загрузки.
    """
    progress_message = await message.reply_text("Начинаю загрузку...", parse_mode=ParseMode.HTML)
    
    while file_id in DOWNLOAD_PROGRESS:
        progress_text = DOWNLOAD_PROGRESS[file_id]
        if total_videos > 1:
            progress_text = f"Загрузка {current_video_num}/{total_videos}: {progress_text}"
        await progress_message.edit_text(
            f"📥 **Идёт загрузка...**\n`{progress_text}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(2) # Обновляем каждые 2 секунды
    
    await progress_message.delete()

async def download_and_send_video(client, message, url, format_id, is_premium):
    """
    Скачивает и отправляет одиночное видео.
    """
    try:
        ydl_opts = {
            'format': format_id,
            'outtmpl': '%(title)s.%(ext)s',
            'progress_hooks': [progress_hook]
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            filesize = info_dict.get('filesize', 0)
            
            file_limit = 4 * 1024 * 1024 * 1024 if is_premium else 2 * 1024 * 1024 * 1024
            
            if filesize > file_limit:
                if is_premium:
                    await message.reply_text("⚠️ **Файл слишком большой!**\nЛимит для Premium-аккаунта 4 ГБ.", parse_mode=ParseMode.MARKDOWN)
                else:
                    await message.reply_text("⚠️ **Файл слишком большой!**\nЛимит для обычного аккаунта 2 ГБ. Получите Premium для скачивания больших файлов.", parse_mode=ParseMode.MARKDOWN)
                return
            
            file_id = info_dict['id']
            # Запускаем таску для отображения прогресса
            progress_task = asyncio.create_task(send_download_progress(message, file_id, 1, 1))

            ydl.download([url])
            
            video_title = info_dict.get('title', 'video')
            filename = ydl.prepare_filename(info_dict)
            
            await client.send_document(
                chat_id=message.chat.id,
                document=filename,
                caption=f"🎥 **{video_title}**\n\n🎉 Ваш файл готов!",
                parse_mode=ParseMode.MARKDOWN
            )

            if file_id in DOWNLOAD_PROGRESS:
                del DOWNLOAD_PROGRESS[file_id]

            os.remove(filename)

    except errors.FloodWait as e:
        await message.reply_text(f"Слишком много запросов. Пожалуйста, подождите {e.value} секунд...", parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Ошибка при загрузке: {e}")
        await message.reply_text("Произошла ошибка. Пожалуйста, проверьте ссылку.", parse_mode=ParseMode.HTML)


async def download_playlist(client, message, url, is_premium):
    """
    Скачивает и отправляет все видео из плейлиста.
    """
    if not is_premium:
        await message.reply_text("⚠️ **Загрузка плейлистов доступна только для Premium-подписчиков.**\nЧтобы получить доступ, оформите подписку.", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        await message.reply_text("Начинаю загрузку плейлиста. Это может занять много времени...")
        
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': '%(playlist_index)s - %(title)s.%(ext)s',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            
            if 'entries' not in playlist_info:
                await message.reply_text("Не удалось найти видео в этом плейлисте.", parse_mode=ParseMode.HTML)
                return

            total_videos = len(playlist_info['entries'])
            
            for i, video_info in enumerate(playlist_info['entries']):
                video_url = video_info['url']
                video_title = video_info['title']
                video_id = video_info['id']

                # Здесь можно добавить логику "Продолжить скачивание?" каждые 100 видео
                if (i + 1) % 100 == 0:
                    # Логика с кнопками для продолжения
                    pass

                await download_and_send_video(client, message, video_url, 'bestvideo+bestaudio/best', is_premium)
                
    except Exception as e:
        logging.error(f"Ошибка при загрузке плейлиста: {e}")
        await message.reply_text("Произошла ошибка при загрузке плейлиста.", parse_mode=ParseMode.HTML)


async def handle_web_app_data(client, message, is_premium):
    """
    Обрабатывает данные, полученные из Web App.
    """
    try:
        data = json.loads(message.web_app_data.data)
        url = data.get('url')
        format_id = data.get('format_id')
        
        if url and format_id:
            await download_and_send_video(client, message, url, format_id, is_premium)
        else:
            await message.reply_text("Неверные данные из Web App.", parse_mode=ParseMode.HTML)

    except json.JSONDecodeError:
        await message.reply_text("Ошибка обработки данных из Web App.", parse_mode=ParseMode.HTML)