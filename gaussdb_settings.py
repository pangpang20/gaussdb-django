#!/usr/bin/env python3

# Copyright (c) 2025, HuaweiCloudDeveloper
# Licensed under the BSD 3-Clause License.
# See LICENSE file in the project root for full license information.

import os

hosts = os.getenv("GAUSSDB_HOST", "127.0.0.1")
port = os.getenv("GAUSSDB_PORT", 5432)
user = os.getenv("GAUSSDB_USER", "postgres")
password = os.getenv("GAUSSDB_PASSWORD", "Audaque@123")

DATABASES = {
    "default": {
        "ENGINE": "gaussdb_django",
        "USER": user,
        "PASSWORD": password,
        "HOST": hosts,
        "PORT": port,
        "NAME": "django_tests01",
        "OPTIONS": {},
    },
    "other": {
        "ENGINE": "gaussdb_django",
        "USER": user,
        "PASSWORD": password,
        "HOST": hosts,
        "PORT": port,
        "NAME": "django_tests02",
        "OPTIONS": {},
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = False
SECRET_KEY = "django_tests_secret_key"

# Use a fast hasher to speed up tests.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
