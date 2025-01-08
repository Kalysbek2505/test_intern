FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl jq \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем файлы приложения
COPY app/requirements.txt /app/requirements.txt

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY /app/.env /app/.env

COPY app/tg_account.py /app/tg_account.py
# Указываем команду для запуска приложения
CMD ["python", "tg_account.py"]