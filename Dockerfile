# Используем официальный образ Python как базовый
FROM python:3.11-slim

# Устанавливаем ffmpeg, необходимый для yt-dlp
RUN apt-get update && apt-get install -y ffmpeg

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальные файлы (код бота, html, js) в контейнер
COPY . .

# Запускаем бота
CMD ["python", "main.py"]