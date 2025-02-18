# Вказуємо базовий образ
FROM python:3.11-slim

# Встановлюємо робочу директорію в контейнері
WORKDIR /app

# Оновлюємо пакети та встановлюємо необхідні бібліотеки (git потрібен для pip install з GitHub)
RUN apt-get update && apt-get install -y git libpq-dev && rm -rf /var/lib/apt/lists/*

# Копіюємо файли проєкту в контейнер
COPY .. /app/

# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir git+https://github.com/liqpay/sdk-python#egg=liqpay-python

# Вказуємо команду для запуску проєкту (запуск Django + main.py)
CMD ["sh", "-c", "python main.py & python manage.py runserver 0.0.0.0:8000"]

