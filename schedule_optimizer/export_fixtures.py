#Скрипт для выгрузки данных из БД в fixtures/data.json.	
#скрипт для того, чтобы можно было быстро восстановить старые данные с командой python manage.py loaddata data.json.

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schedule_optimizer.settings')
django.setup()

from django.core import serializers
from django.apps import apps

print("💾 НАДЕЖНЫЙ ЭКСПОРТ ФИКСТУР (кириллица-safe)")
print("=" * 50)

# Исключаем системные таблицы
EXCLUDE_MODELS = [
    'contenttypes.contenttype',
    'auth.permission',
    'sessions.session',
    'admin.logentry',  # Часто содержит проблемы с кодировкой
]

# Собираем все объекты
all_objects = []
for app_config in apps.get_app_configs():
    for model in app_config.get_models():
        model_label = f"{app_config.label}.{model.__name__.lower()}"
        if model_label not in EXCLUDE_MODELS:
            objects = list(model.objects.all())
            if objects:
                all_objects.extend(objects)
                print(f"✅ {model_label:30} ({len(objects)} объектов)")

print(f"\n📦 Всего объектов: {len(all_objects)}")

# Сохраняем с корректной кодировкой (КЛЮЧЕВОЙ ПАРАМЕТР: ensure_ascii=False)
try:
    os.makedirs('fixtures', exist_ok=True)

    with open('fixtures/data.json', 'w', encoding='utf-8') as f:
        serializers.serialize(
            'json',
            all_objects,
            indent=2,
            stream=f,
            ensure_ascii=False,  # ← ЭТО ГАРАНТИРУЕТ СОХРАНЕНИЕ КИРИЛЛИЦЫ КАК ЕСТЬ!
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True
        )

    # Проверка результата
    size_mb = os.path.getsize('fixtures/data.json') / 1024 / 1024
    print(f"\n✅ УСПЕХ! Файл сохранен в UTF-8")
    print(f"📄 fixtures/data.json ({size_mb:.2f} MB)")

    # Быстрая проверка первых строк
    with open('fixtures/data.json', 'r', encoding='utf-8') as f:
        preview = f.read(300)
        if "январь" in preview or "февраль" in preview or "Понедельник" in preview:
            print("✅ Кириллица сохранена корректно")
        elif "\\u04" in preview[:100]:
            print("⚠️  Данные в Unicode-escape (нормально для JSON, но читаемость ниже)")
        else:
            print("❓ Проверьте файл в редакторе (VS Code / PyCharm)")

except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n👉 Далее выполните:")
print("   git add fixtures/data.json")
print("   git commit -m \"fix: фикстуры с корректной кириллицей\"")
print("   git push")
print("=" * 50)