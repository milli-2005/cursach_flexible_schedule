"""Основные настройки Django-проекта: приложения, база данных, статика, почта и фоновые задачи."""

import os
from pathlib import Path
from celery.schedules import crontab

# Базовая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """Простой загрузчик .env для локального запуска без дополнительных библиотек."""
    if not path.exists():
        return
    override_existing = not Path('/.dockerenv').exists()
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        # Защита от BOM в начале файла и от пробелов.
        key = key.strip().lstrip('\ufeff')
        # Убираем inline-комментарий вида "KEY=value # comment", если он не в кавычках.
        value = value.strip()
        if '#' in value and not (value.startswith('"') or value.startswith("'")):
            value = value.split('#', 1)[0].rstrip()
        value = value.strip('"').strip("'")
        if override_existing:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


_load_env_file(BASE_DIR / '.env')


# Настройки для разработки (не для production)
SECRET_KEY = 'django-insecure-6^86^l($y=q_)sj8+5^&i(vsupzj8npwvk-))!xqe)e&3iu=f^'
DEBUG = True
ALLOWED_HOSTS = []


# Приложения
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
]


# Промежуточные обработчики (middleware)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'core.middleware.FriendlyErrorMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.ForcePasswordChangeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'schedule_optimizer.urls'


# Шаблоны
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.pending_schedule_approval_notice',
                'core.context_processors.manager_schedule_feedback_notice',
            ],
        },
    },
]

WSGI_APPLICATION = 'schedule_optimizer.wsgi.application'


def _env_bool(name: str, default: bool = False) -> bool:
    """Преобразует строковое значение переменной окружения в boolean."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


# База данных
USE_POSTGRES = _env_bool('USE_POSTGRES', default=False)
RULE_AI_ENABLED = _env_bool('RULE_AI_ENABLED', default=False)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '').strip()
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.4-mini').strip() or 'gpt-5.4-mini'

if USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'schedule_optimizer'),
            'USER': os.getenv('POSTGRES_USER', 'postgres'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': int(os.getenv('POSTGRES_CONN_MAX_AGE', '60')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Валидация паролей
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Локализация
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True


# Статика
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Медиа-файлы
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Первичный ключ по умолчанию
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Редиректы авторизации
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'index'
LOGIN_URL = 'login'


# Логирование
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '{levelname} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'core': {'handlers': ['console'], 'level': 'INFO', 'propagate': True},
    },
}


# Настройки почты (значения берутся из .env) 
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' #Django будет отправлять письма через SMTP
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com') #Берет EMAIL_HOST из .env; если пусто, подставит smtp.gmail.com.
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '465')) #Берет порт из .env, по умолчанию 465
EMAIL_USE_SSL = EMAIL_PORT == 465 #Если порт 465, включается SSL.
EMAIL_USE_TLS = not EMAIL_USE_SSL #Если SSL выключен, включается TLS (обычно для порта 587)
EMAIL_TIMEOUT = 25 #Таймаут соединения 25 секунд.
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '').strip() #Логин SMTP (почта) из .env
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '').strip()
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@localhost') #Отправитель из .env, иначе EMAIL_HOST_USER, иначе запасной no-reply@localhost.


# Расписание задач Celery Beat
CELERY_BEAT_SCHEDULE = {
    'send-availability-reminder': {
        'task': 'core.tasks.send_availability_reminder',
        'schedule': crontab(day_of_week=1, hour=18, minute=0),  # Вторник, 18:00
    },
    'auto-approve-schedules': {
        'task': 'core.tasks.auto_approve_schedules',
        'schedule': 600.0,  # Каждые 10 минут
    },
}

print('LOGGING загружен')
