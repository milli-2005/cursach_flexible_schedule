#!/usr/bin/env python3
import subprocess
import sys
import os

print("💾 СОХРАНЕНИЕ ДАННЫХ ДЛЯ GIT (UTF-8)")
print("=" * 40)

# Принудительно устанавливаем UTF-8 кодировку для Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

try:
    # Переходим в директорию проекта Django
    if not os.path.exists("schedule_optimizer"):
        print("❌ Директория schedule_optimizer не найдена. Запускайте скрипт из корня проекта.")
        sys.exit(1)

    os.chdir("schedule_optimizer")

    # Формируем команду с правильной кодировкой
    cmd = [
        sys.executable, "manage.py", "dumpdata",
        "--indent", "2",
        "--exclude", "contenttypes",
        "--exclude", "auth.permission",
        "--exclude", "sessions.session",
        "--exclude", "admin.logentry",  # Исключаем логи админа (часто с проблемами кодировки)
        "--natural-foreign",
        "--natural-primary",
        "-o", "fixtures/data.json"
    ]

    print("Выполняется экспорт данных...")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'  # Игнорируем проблемные символы при выводе
    )

    if result.returncode != 0:
        print("❌ Ошибка при экспорте:")
        print(result.stderr)
        # Попробуем альтернативный метод через перенаправление в файл
        print("\n🔄 Пробуем альтернативный метод...")
        with open("fixtures/data.json", "w", encoding="utf-8") as f:
            subprocess.run(
                cmd[:-2],  # Без -o и имени файла
                stdout=f,
                encoding='utf-8',
                errors='replace'
            )
        print("✅ Данные сохранены альтернативным методом")
    else:
        print("✅ Данные успешно экспортированы в UTF-8")

    # Проверяем размер файла
    if os.path.exists("fixtures/data.json"):
        size_mb = os.path.getsize("fixtures/data.json") / 1024 / 1024
        print(f"📄 Размер файла: {size_mb:.2f} MB")

        # Быстрая проверка первых строк на кириллицу
        with open("fixtures/data.json", "r", encoding="utf-8", errors='replace') as f:
            preview = f.read(500)
            if "" in preview or "\\u04" in preview[:200]:
                print("⚠️  Внимание: в файле могут быть проблемы с кодировкой")
                print("   Рекомендуется проверить файл в редакторе (VS Code / PyCharm)")
            else:
                print("✅ Кодировка выглядит корректной")

except Exception as e:
    print(f"❌ Критическая ошибка: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n👉 Теперь выполните:")
print("   git add fixtures/data.json")
print("   git commit -m \"fix: обновлён дамп данных с корректной кодировкой UTF-8\"")
print("   git push")
print("=" * 40)