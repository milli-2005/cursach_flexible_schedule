#!/usr/bin/env python3
import subprocess
import sys
import os

print("💾 СОХРАНЕНИЕ ДАННЫХ ДЛЯ GIT")
print("="*40)

# Сохраняем БЕЗ системных таблиц (чтобы не было конфликтов)
os.chdir("schedule_optimizer")
subprocess.run([
    sys.executable, "manage.py", "dumpdata",
    "--indent", "2",
    "--exclude", "contenttypes",
    "--exclude", "auth.permission",
    "--exclude", "sessions.session",
    "-o", "fixtures/data.json"
])

print("✅ Данные сохранены в fixtures/data.json")
print("👉 Теперь выполни: git add . && git commit && git push")
print("="*40)