
"""
Django settings for config project.

ASTRA TECH
Django 6.0.7
Local  : SQLite
Vercel : PostgreSQL / Neon
"""

from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv


# ============================================================
# CHARGEMENT DU .env
# ============================================================

load_dotenv()


# ============================================================
# BASE DIR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# ENVIRONNEMENT
# ============================================================

# Vercel définit généralement cette variable automatiquement.
IS_VERCEL = os.getenv("VERCEL", "").lower() in {
    "1",
    "true",
    "yes",
}

# DEBUG
DEBUG = os.getenv("DEBUG", "False").lower() in {
    "1",
    "true",
    "yes",
}


# ============================================================
# SECURITY
# ============================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-key-change-in-production",
)

# En production, il est fortement recommandé de définir
# SECRET_KEY dans les variables d'environnement Vercel.

if IS_VERCEL and SECRET_KEY == "django-insecure-dev-key-change-in-production":
    raise RuntimeError(
        "SECRET_KEY n'est pas configurée sur Vercel. "
        "Ajoutez une variable SECRET_KEY dans Vercel."
    )


# ============================================================
# ALLOWED HOSTS
# ============================================================

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".vercel.app",
]

# Autoriser éventuellement des domaines personnalisés
EXTRA_ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "",
).strip()

if EXTRA_ALLOWED_HOSTS:
    ALLOWED_HOSTS.extend(
        host.strip()
        for host in EXTRA_ALLOWED_HOSTS.split(",")
        if host.strip()
    )


# ============================================================
# CSRF
# ============================================================

CSRF_TRUSTED_ORIGINS = [
    # Local
    "http://localhost:8000",
    "http://127.0.0.1:8000",

    # Réseau local
    "http://192.168.0.119:8000",

    # Vercel
    "https://*.vercel.app",

    # Serveo
    "https://*.serveo.net",
    "https://*.serveousercontent.com",
]


# Ajouter les origines personnalisées depuis .env / Vercel
EXTRA_CSRF_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "",
).strip()

if EXTRA_CSRF_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(
        origin.strip()
        for origin in EXTRA_CSRF_ORIGINS.split(",")
        if origin.strip()
    )


# ============================================================
# HTTPS / PROXY VERCEL
# ============================================================

# Vercel termine le HTTPS avant de transmettre la requête
# à Django.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)


# Cookies sécurisés uniquement en HTTPS
SESSION_COOKIE_SECURE = IS_VERCEL or not DEBUG
CSRF_COOKIE_SECURE = IS_VERCEL or not DEBUG


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # ASTRA TECH
    "astra",
    "boutique",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # Static files
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # Sessions
    "django.contrib.sessions.middleware.SessionMiddleware",

    # Common
    "django.middleware.common.CommonMiddleware",

    # CSRF
    "django.middleware.csrf.CsrfViewMiddleware",

    # Authentication
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # Messages
    "django.contrib.messages.middleware.MessageMiddleware",

    # Clickjacking
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Middleware ASTRA volontairement désactivé
    # afin d'éviter les blocages globaux.
    #
    # "astra.middleware.VerrouillageGlobalMiddleware",
]


# ============================================================
# URL CONFIGURATION
# ============================================================

ROOT_URLCONF = "config.urls"


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                # Notifications ASTRA TECH
                "astra.context_processors.notifications_processor",
            ],
        },
    },
]


# ============================================================
# WSGI
# ============================================================

WSGI_APPLICATION = "config.wsgi.application"


# ============================================================
# DATABASE
# ============================================================
#
# LOCAL
# -----
# SQLite
#
# VERCEL
# ------
# PostgreSQL / Neon
#
# Variables possibles :
#
# DATABASE_URL
# POSTGRES_URL_NON_POOLING
# POSTGRES_URL
#
# ============================================================


# ------------------------------------------------------------
# PostgreSQL
# ------------------------------------------------------------

POSTGRES_DATABASE_URL = (
    os.getenv("POSTGRES_URL_NON_POOLING")
    or os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or ""
).strip()


# ------------------------------------------------------------
# Turso — conservé uniquement si tu souhaites encore
# l'utiliser plus tard.
# ------------------------------------------------------------

USE_TURSO = os.getenv(
    "USE_TURSO",
    "False",
).lower() in {
    "1",
    "true",
    "yes",
}

TURSO_DATABASE_URL = os.getenv(
    "TURSO_DATABASE_URL",
    "",
).strip()

TURSO_AUTH_TOKEN = os.getenv(
    "TURSO_AUTH_TOKEN",
    "",
).strip()


# ============================================================
# DATABASE SELECTION
# ============================================================

if POSTGRES_DATABASE_URL:

    # ========================================================
    # PRODUCTION
    # PostgreSQL / Neon
    # ========================================================

    DATABASES = {
        "default": dj_database_url.parse(
            POSTGRES_DATABASE_URL,
            conn_max_age=0,
            ssl_require=True,
        )
    }


elif IS_VERCEL:

    # ========================================================
    # VERCEL SANS DATABASE
    # ========================================================
    #
    # On refuse de démarrer avec SQLite sur Vercel.
    #
    # SQLite sur le filesystem Vercel n'est pas adapté
    # à une base de données persistante.
    #
    # ========================================================

    raise RuntimeError(
        "Aucune base PostgreSQL configurée sur Vercel. "
        "Ajoutez DATABASE_URL ou POSTGRES_URL_NON_POOLING "
        "dans les variables d'environnement Vercel."
    )


elif USE_TURSO and TURSO_DATABASE_URL:

    # ========================================================
    # OPTION TURSO
    # ========================================================

    DATABASES = {
        "default": {
            "ENGINE": "django_libsql",
            "NAME": TURSO_DATABASE_URL,
            "AUTH_TOKEN": TURSO_AUTH_TOKEN,
            "OPTIONS": {
                "timeout": 60,
            },
        }
    }


else:

    # ========================================================
    # LOCAL
    # SQLite
    # ========================================================

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = "Africa/Douala"

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]


# WhiteNoise
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)


# ============================================================
# MEDIA FILES
# ============================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# EMAIL
# ============================================================

EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
)

EMAIL_HOST = os.getenv(
    "EMAIL_HOST",
    "smtp.gmail.com",
)

EMAIL_PORT = int(
    os.getenv(
        "EMAIL_PORT",
        "587",
    )
)

EMAIL_USE_TLS = (
    os.getenv(
        "EMAIL_USE_TLS",
        "True",
    ).lower()
    in {"1", "true", "yes"}
)

EMAIL_HOST_USER = os.getenv(
    "EMAIL_HOST_USER",
    "",
)

EMAIL_HOST_PASSWORD = os.getenv(
    "EMAIL_HOST_PASSWORD",
    "",
)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER,
)


# ============================================================
# AUTHENTIFICATION
# ============================================================

LOGIN_URL = "astra:login"

LOGIN_REDIRECT_URL = "astra:accueil"

LOGOUT_REDIRECT_URL = "astra:login"


# ============================================================
# SESSIONS
# ============================================================

# Sessions stockées dans la base de données.
#
# En local :
# SQLite
#
# Sur Vercel :
# PostgreSQL / Neon
#
SESSION_ENGINE = (
    "django.contrib.sessions.backends.db"
)

# 2 semaines
SESSION_COOKIE_AGE = 1209600

# Met à jour la session à chaque requête.
SESSION_SAVE_EVERY_REQUEST = True

# Protection JavaScript
SESSION_COOKIE_HTTPONLY = True

# Protection cross-site
SESSION_COOKIE_SAMESITE = "Lax"

# HTTPS
SESSION_COOKIE_SECURE = (
    IS_VERCEL or not DEBUG
)


# ============================================================
# CSRF COOKIE
# ============================================================

CSRF_COOKIE_HTTPONLY = False

CSRF_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = (
    IS_VERCEL or not DEBUG
)


# ============================================================
# SECURITY HEADERS
# ============================================================

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_BROWSER_XSS_FILTER = True

X_FRAME_OPTIONS = "DENY"


# HTTPS uniquement en production
if IS_VERCEL or not DEBUG:

    SECURE_SSL_REDIRECT = True

    SECURE_HSTS_SECONDS = 31536000

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = True

else:

    SECURE_SSL_REDIRECT = False

    SECURE_HSTS_SECONDS = 0

    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

    SECURE_HSTS_PRELOAD = False


# ============================================================
# DEFAULT PRIMARY KEY
# ============================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)
