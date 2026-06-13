# Структура проекта

Проект построен на Django. Основная логика находится в приложении `core`.

## Главные папки

- `schedule_optimizer/` - настройки Django-проекта: `settings.py`, главный `urls.py`, `asgi.py`, `wsgi.py`.
- `core/` - основное приложение системы сменного расписания.
- `templates/core/` - HTML-шаблоны интерфейса.
- `static/` - CSS, JS и статические изображения.
- `media/` - загруженные пользователями файлы, например аватары.

## Приложение core

- `core/models/` - модели базы данных: пользователи, сотрудники, графики, смены, чат, заявки.
- `core/views/` - обычные страницы интерфейса, разложенные по разделам.
- `core/api/` - JSON API для динамических действий на страницах.
- `core/forms/` - Django-формы.
- `core/exports/` - генерация файлов для скачивания, сейчас Excel-табель.
- `core/services/` - вспомогательная бизнес-логика и интеграции.
- `core/urls.py` - карта всех маршрутов приложения, разбитая по разделам.
- `core/context_processors.py` - уведомления, которые доступны в шаблонах.
- `core/middleware.py` - промежуточная логика запросов, например принудительная смена временного пароля.
- `core/tasks.py` - фоновые задачи Celery.
- `core/error_handlers.py` и `core/error_utils.py` - обработка ошибок.

## Основные домены

- Пользователи и сотрудники: `UserProfile`, `Employee`, API в `core/api/user_views.py`.
- Графики: `Schedule`, `ShiftAssignment`, версии графиков, согласование и API в `core/api/schedule_views.py`.
- Доступность: `Availability`, страница `my_availability`.
- Обмен сменами: `ShiftSwapRequest`, `SwapShift`, API в `core/api/swap_views.py`.
- Занятия: `WorkoutType`, API в `core/api/workout_views.py`.
- Чат: модели `ChatConversation`, `ChatMessage`, API в `core/api/chat_views.py`.
- Отчеты: страница отчетов в `core/views/`, Excel-экспорт в `core/exports/operational_excel.py`.

## Страницы интерфейса

- `core/views/public.py` - главная страница, страница о системе и страница чата.
- `core/views/auth.py` - вход, выход и смена временного пароля.
- `core/views/users.py` - приглашение пользователей, управление пользователями, сброс пароля.
- `core/views/profile.py` - просмотр и редактирование личного профиля.
- `core/views/dashboard.py` - личные кабинеты для ролей.
- `core/views/schedules.py` - страницы создания, просмотра, редактирования и удаления графиков.
- `core/views/availability.py` - доступность сотрудников и ручная отправка напоминаний.
- `core/views/distribution_rules.py` - правила распределения занятий.
- `core/views/workouts.py` - страница типов занятий.
- `core/views/swaps.py` - страницы заявок и обмена сменами.
- `core/views/reports.py` - страница отчетов.
- `core/views/common.py` - общие импорты и небольшие helper-функции для views.
- `core/views/__init__.py` - переэкспортирует views, чтобы старые импорты и URL продолжали работать.

## Важные проверки

После структурных изменений запускать:

```powershell
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Первая команда проверяет Django-проект, вторая подтверждает, что структура моделей не изменила схему базы данных.
