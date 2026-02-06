# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем пакеты
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Собираем статику (если используешь collectstatic)
RUN python manage.py collectstatic --noinput

# Открываем порт
EXPOSE 8000

# Запуск
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]