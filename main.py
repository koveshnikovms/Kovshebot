import os
import logging
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Включаем логирование, чтобы видеть ошибки
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Получаем токен из переменных окружения (так безопаснее)
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Словарь с инструментами, которые будем отслеживать
# Вы можете менять тикеры и названия здесь
INSTRUMENTS = {
    "RTS": {"name": "Фьючерс RTS", "board": "RTS", "market": "forts"},
    "USD000UTSTOM": {"name": "Доллар/Рубль", "board": "CETS", "market": "selt"},
    "BTC": {"name": "Фьючерс BTC", "board": "RFUD", "market": "forts"}
}

async def get_price(session: aiohttp.ClientSession, ticker: str, info: dict):
    """Асинхронно получает цену с MOEX ISS API"""
    # Формируем URL для запроса к API Мосбиржи
    # Мы запрашиваем marketdata для конкретного тикера на конкретном рынке
    url = f"https://iss.moex.com/iss/engines/stock/markets/{info['market']}/boards/{info['board']}/securities/{ticker}.json"
    
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                # Данные приходят в сложной структуре, нам нужна таблица 'marketdata'
                marketdata = data.get('marketdata', {})
                if marketdata and 'data' in marketdata and len(marketdata['data']) > 0:
                    # Ищем колонку с последней ценой (LAST) или расчетной ценой
                    columns = marketdata['columns']
                    row = marketdata['data'][0]
                    
                    # Пытаемся найти LAST, если нет — берем любую доступную цену
                    if 'LAST' in columns:
                        idx = columns.index('LAST')
                        price = row[idx]
                    elif 'LCURRENTPRICE' in columns:
                        idx = columns.index('LCURRENTPRICE')
                        price = row[idx]
                    elif 'SETTLEPRICE' in columns:
                         idx = columns.index('SETTLEPRICE')
                         price = row[idx]
                    else:
                        return f"{info['name']}: Цена не найдена (торги не идут?)"
                    
                    if price is not None:
                        return f"{info['name']}: {price}"
                    else:
                        return f"{info['name']}: Нет данных (возможно, торги закрыты)"
    except Exception as e:
        logging.error(f"Ошибка при запросе {ticker}: {e}")
        return f"{info['name']}: Ошибка соединения"

    return f"{info['name']}: Нет данных"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text("Привет! Сейчас посмотрю цены на Мосбирже...")
    
    # Создаем сессию для HTTP-запросов
    async with aiohttp.ClientSession() as session:
        tasks = []
        for ticker, info in INSTRUMENTS.items():
            tasks.append(get_price(session, ticker, info))
        
        # Выполняем все запросы параллельно
        results = await asyncio.gather(*tasks)
        
        # Формируем ответ
        response_text = "📊 *Текущие котировки:*\n\n" + "\n".join(results)
        await update.message.reply_text(response_text, parse_mode='Markdown')

def main():
    """Запуск бота"""
    if not TOKEN:
        print("Ошибка: Не найден TELEGRAM_TOKEN. Убедитесь, что переменная окружения установлена.")
        return

    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчик команды /start
    application.add_handler(CommandHandler("start", start))
    
    print("Бот запущен и работает...")
    application.run_polling()

if __name__ == '__main__':
    main()