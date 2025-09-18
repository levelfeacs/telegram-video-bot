document.getElementById('downloadBtn').addEventListener('click', () => {
    const url = document.getElementById('urlInput').value;
    if (url) {
        // Отправляем ссылку боту
        Telegram.WebApp.sendData(url);
        Telegram.WebApp.close(); // Закрываем Web App
    }
});