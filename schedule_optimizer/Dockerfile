#2 шаг 

# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем рабочую папку внутри контейнера
WORKDIR /app

#Сначала копируем только список зависимостей
COPY requirements.txt .

# Устанавливаем их
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Собираем статику (если используешь collectstatic)
RUN python manage.py collectstatic --noinput

# Говорим: "контейнер слушает порт 8000"
EXPOSE 8000

# Запуск, команды при старте
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]