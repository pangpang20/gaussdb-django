#!/usr/bin/env python3

# Copyright (c) 2025, HuaweiCloudDeveloper
# Licensed under the BSD 3-Clause License.
# See LICENSE file in the project root for full license information.

import os

GAUSSDB_DRIVER_HOME = "/opt/gaussdb_driver"

ld_path = os.path.join(GAUSSDB_DRIVER_HOME, "hce_driver", "lib")
os.environ["LD_LIBRARY_PATH"] = f"{ld_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"

os.environ.setdefault("GAUSSDB_IMPL", "python")


hosts = os.getenv("GAUSSDB_HOST", "192.168.0.58")
port = os.getenv("GAUSSDB_PORT", 8000)
# hosts = os.getenv("GAUSSDB_HOST", "127.0.0.1")
# port = os.getenv("GAUSSDB_PORT", 8888)
user = os.getenv("GAUSSDB_USER", "root")
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

# from django.db.models.query import QuerySet

# def patched_batched_insert(self, objs, fields, returning_fields, *args, **kwargs):
#     print(f"[GaussDB Patch] bulk_insert called: {len(objs)} objs, returning_fields={returning_fields}")

#     returned_columns = []
#     for obj in objs:
#         try:
#             res = self._insert([obj], fields, returning_fields, *args, **kwargs)
#             if res:
#                 returned_columns.extend(res)
#         except Exception as e:
#             print(f"[GaussDB Patch] Insert failed for {obj}: {e}")
#             returned_columns.append([None])

#     if not returned_columns:
#         returned_columns = [[None] for _ in objs]

#     if len(returned_columns) != len(objs):
#         print(f"[GaussDB Patch] correcting length: got {len(returned_columns)}, need {len(objs)}")
#         while len(returned_columns) < len(objs):
#             returned_columns.append([None])
#         returned_columns = returned_columns[:len(objs)]

#     return returned_columns

# QuerySet._batched_insert = patched_batched_insert