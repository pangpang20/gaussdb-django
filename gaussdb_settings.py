#!/usr/bin/env python3

# Copyright (c) 2025, HuaweiCloudDeveloper
# Licensed under the BSD 3-Clause License.
# See LICENSE file in the project root for full license information.

import os
import tempfile

GAUSSDB_DRIVER_HOME = "/tmp"

ld_path = os.path.join(GAUSSDB_DRIVER_HOME, "lib")
os.environ["LD_LIBRARY_PATH"] = f"{ld_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"

os.environ.setdefault("GAUSSDB_IMPL", "python")

hosts = os.getenv("GAUSSDB_HOST", "127.0.0.1")
port = os.getenv("GAUSSDB_PORT", 5432)
user = os.getenv("GAUSSDB_USER", "root")
password = os.getenv("GAUSSDB_PASSWORD", "Passwd@123")

DATABASES = {
    "default": {
        "ENGINE": "gaussdb_django",
        "NAME": "gaussdb_default",
        "USER": user,
        "PASSWORD": password,
        "HOST": hosts,
        "PORT": port,
        "OPTIONS": {},
        "TEST": {
            "NAME": "test_default",
            "TEMPLATE": "template0",
        },
    },
    "other": {
        "ENGINE": "gaussdb_django",
        "NAME": "gaussdb_other",
        "USER": user,
        "PASSWORD": password,
        "HOST": hosts,
        "PORT": port,
        "OPTIONS": {},
        "TEST": {
            "NAME": "test_other",
            "TEMPLATE": "template0",
        },
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = False
SECRET_KEY = "django_tests_secret_key"

# Use a fast hasher to speed up tests.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/tmp/gaussdb_cache",
    }
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "admin_changelist",
    "migrations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": "/tmp/django_debug.log",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.db.backends": {
            "level": "DEBUG",
            "handlers": ["file", "console"],
        },
    },
}

_old_close = tempfile._TemporaryFileCloser.close


def _safe_close(self):
    try:
        _old_close(self)
    except FileNotFoundError:
        pass


tempfile._TemporaryFileCloser.close = _safe_close
