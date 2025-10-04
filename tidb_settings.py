#!/usr/bin/env python3

# Copyright (c) 2025, HuaweiCloudDeveloper
# Licensed under the BSD 3-Clause License.
# See LICENSE file in the project root for full license information.

import os

hosts = os.getenv("TIDB_HOST", "127.0.0.1")
port = os.getenv("TIDB_PORT", 4000)
user = os.getenv("TIDB_USER", "tidb")
password = os.getenv("TIDB_PASSWORD", "Audaque@123")

DATABASES = {
    "default": {
        "ENGINE": "django_tidb",
        "USER": user,
        "PASSWORD": password,
        "HOST": hosts,
        "PORT": port,
        "TEST": {
            "NAME": "django_tests",
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_general_ci",
        },
        "OPTIONS": {
            "init_command": "SET @@tidb_allow_remove_auto_inc = ON",
        },
    },
    "other": {
        "ENGINE": "django_tidb",
        "USER": user,
        "PASSWORD": password,
        "HOST": hosts,
        "PORT": port,
        "TEST": {
            "NAME": "django_tests2",
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_general_ci",
        },
        "OPTIONS": {
            "init_command": "SET @@tidb_allow_remove_auto_inc = ON",
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
