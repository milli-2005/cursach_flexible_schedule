#!/usr/bin/env python3
import os
import subprocess
import sys

def main():
    print("=" * 50)
    print("🚀 АВТОМАТИЧЕСКАЯ УСТАНОВКА SCHEDULE SCHEDULER")
    print("=" * 50)
    
    # Проверяем виртуальное окружение
    if not os.path.exists(".venv"):
        print("\n📦 Создаю виртуальное окружение...")
        subprocess.run([sys.executable, "-m", "venv", ".venv"])
    
    # Активируем venv (для зависимостей)
    if os.name == 'nt':  # Windows
        python_path = ".venv\\Scripts\\python"
        pip_path = ".venv\\Scripts\\pip"
    else:  # Linux/Mac
        python_path = ".venv/bin/python"
        pip_path = ".venv/bin/pip"
    
    print("\n📦 Устанавливаю Django...")
    subprocess.run([pip_path, "install", "django"])
    
    print("\n🔄 Создаю базу данных...")
    os.chdir("schedule_optimizer")
    subprocess.run([python_path, "manage.py", "migrate"])
    
    if os.path.exists("fixtures/data.json"):
        print("\n💾 Загружаю сохраненные данные...")
        subprocess.run([python_path, "manage.py", "loaddata", "data.json"])
    
    print("\n" + "=" * 50)
    print("✅ УСТАНОВКА ЗАВЕРШЕНА!")
    print("\n👉 Чтобы запустить сервер, выполни:")
    print("   cd schedule_optimizer")
    print("   python manage.py runserver")
    print("\n👉 Затем открой в браузере:")
    print("   http://127.0.0.1:8000")
    print("=" * 50)

if __name__ == "__main__":
    main()
