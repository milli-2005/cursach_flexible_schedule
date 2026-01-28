#!/usr/bin/env python3
import subprocess
import sys
import os

print("💾 Автоматическое сохранение базы данных...")
os.chdir("schedule_optimizer")
subprocess.run([sys.executable, "manage.py", "dumpdata", "--indent", "2", "-o", "fixtures/data.json"])
print("✅ Все данные сохранены в fixtures/data.json")
print("   Не забудь: git add schedule_optimizer/fixtures/data.json")
