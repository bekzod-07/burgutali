"""
Umumiy Django sozlamalari.

Bu fayl dev va prod sozlamalari uchun asos bo'lib xizmat qiladi.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from core.env import (
    BASE_DIR,
    get_bool,
    get_int,
    get_list,
    get_str,
    load_env,
)

load_env()

# ==========================================================================
#  Yo'llar
# ==========================================================================
BASE_DIR: Path = BASE_DIR  # noqa: PLW0127 - qulaylik uchun qayta e'lon

DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
LOGS_DIR = BASE_DIR / "logs"
ASSETS_DIR = BASE_DIR / "assets"

for _directory in (DATA_DIR, MEDIA_DIR, LOGS_DIR):
    _directory.mkdir(parents=True, exist_ok=True)


# ==========================================================================
#  Asosiy
# ==========================================================================
SECRET_KEY = get_str("DJANGO_SECRET_KEY", "dev-only-insecure-key-o-zgartiring")
DEBUG = get_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"])
CSRF_TRUSTED_ORIGINS = get_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==========================================================================
#  Ilovalar
# ==========================================================================
#: `django.contrib.admin` ataylab ishlatilmaydi — barcha boshqaruv
#: `apps.dashboard` dagi o'z panelimiz orqali amalga oshiriladi.
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

LOCAL_APPS = [
    "apps.common",
    "apps.users",
    "apps.exams",
    "apps.attempts",
    "apps.accesscodes",
    "apps.rasch",
    "apps.certificates",
    "apps.exports",
    "apps.miniapp",
    "apps.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS


# ==========================================================================
#  Middleware
# ==========================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Mini App sahifalari Telegram iframe ichida ochilishi uchun.
    # Diqqat: javob middleware'lari teskari tartibda ishlaydi, shuning uchun
    # bu qator `XFrameOptionsMiddleware` dan YUQORIDA turishi shart —
    # aks holda u qo'yilgan sarlavhani olib tashlay olmaydi.
    "apps.common.middleware.TelegramFrameMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ==========================================================================
#  Shablonlar
# ==========================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.common.context_processors.site_info",
            ],
        },
    },
]


# ==========================================================================
#  Ma'lumotlar bazasi
# ==========================================================================

def _database_from_url(url: str) -> dict | None:
    """`DATABASE_URL` ni Django DATABASES formatiga o'giradi."""
    if not url:
        return None
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme in {"postgres", "postgresql", "psql", "pgsql"}:
        engine = "django.db.backends.postgresql"
    elif scheme in {"mysql", "mariadb"}:
        engine = "django.db.backends.mysql"
    elif scheme == "sqlite":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": parsed.path.lstrip("/") or str(DATA_DIR / "db.sqlite3"),
        }
    else:
        return None
    return {
        "ENGINE": engine,
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {},
    }


_DB_FROM_URL = _database_from_url(get_str("DATABASE_URL", ""))

if _DB_FROM_URL:
    DATABASES = {"default": _DB_FROM_URL}
else:
    # Standart holat: SQLite. Bot va web bir vaqtda yozishi mumkin bo'lgani
    # uchun WAL rejimi va uzunroq timeout qo'llaniladi
    # (apps/common/db_pragmas.py ga qarang).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DATA_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 30},
        }
    }

USING_SQLITE = DATABASES["default"]["ENGINE"].endswith("sqlite3")


# ==========================================================================
#  Autentifikatsiya (web panel uchun)
# ==========================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/panel/kirish/"
LOGIN_REDIRECT_URL = "/panel/"
LOGOUT_REDIRECT_URL = "/panel/kirish/"

SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

#: Telegram Web da Mini App iframe ichida ochiladi — sessiya cookie'si
#: uchinchi tomon kontekstiga tushadi. Brauzer uni saqlashi uchun
#: `SameSite=None; Secure` kerak (faqat HTTPS da mumkin).
if get_str("PUBLIC_BASE_URL", "").startswith("https://"):
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SECURE = True
else:
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"


# ==========================================================================
#  Til va vaqt
# ==========================================================================
LANGUAGE_CODE = "uz"
TIME_ZONE = get_str("DJANGO_TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True

DATETIME_FORMAT = "d.m.Y H:i"
DATE_FORMAT = "d.m.Y"


# ==========================================================================
#  Statik va media fayllar
# ==========================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [p for p in [BASE_DIR / "static"] if p.exists()]

MEDIA_URL = "/media/"
MEDIA_ROOT = MEDIA_DIR

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# ==========================================================================
#  Telegram bot bilan umumiy sozlamalar
# ==========================================================================
BOT_TOKEN = get_str("BOT_TOKEN", "")
BOT_USERNAME = get_str("BOT_USERNAME", "").lstrip("@")
PUBLIC_BASE_URL = get_str("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED_CHANNEL = get_str("REQUIRED_CHANNEL", "@Burgutali")
REQUIRED_CHANNEL_URL = get_str("REQUIRED_CHANNEL_URL", "https://t.me/Burgutali")

#: Mini App initData imzosining amal qilish muddati (sekund).
MINIAPP_INITDATA_TTL = get_int("MINIAPP_INITDATA_TTL", 24 * 60 * 60)


# ==========================================================================
#  Sertifikat sozlamalari
# ==========================================================================
CERT_ORGANIZATION = get_str("CERT_ORGANIZATION", "Burgutali Math Academy")
CERT_ORGANIZER_NAME = get_str("CERT_ORGANIZER_NAME", "Burgutali Eshquvvatov")
CERT_PLATFORM_NAME = get_str("CERT_PLATFORM_NAME", "RASCH MATH PLATFORM")
CERT_MEDIA_SUBDIR = "certificates"
EXPORT_MEDIA_SUBDIR = "exports"


# ==========================================================================
#  Loglar
# ==========================================================================
LOG_LEVEL = get_str("DJANGO_LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname:<8} {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "app.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
        "aiogram": {"level": "INFO", "propagate": True},
    },
}


# ==========================================================================
#  Xabarlar (messages) — Bootstrap'siz o'z CSS klasslarimiz
# ==========================================================================
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}
