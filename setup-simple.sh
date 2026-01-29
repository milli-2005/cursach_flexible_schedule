#!/bin/bash
echo "🚀 Установка проекта..."
cd schedule_optimizer

# Установка зависимостей
pip install django celery pillow 2>/dev/null || echo "Использую существующие пакеты"

# Миграции
python manage.py migrate

# Загрузка данных если есть
if [ -f "fixtures/data.json" ]; then
    echo "💾 Загружаю данные..."
    python manage.py loaddata data.json
fi

echo "✅ Готово! Запуск: python manage.py runserver"
