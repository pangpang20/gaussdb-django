#!/bin/bash
# Copyright (c) 2025, HuaweiCloudDeveloper
# Licensed under the BSD 3-Clause License.
# See LICENSE file in the project root for full license information.

set -x pipefail

# Disable buffering, so that the logs stream through.
export PYTHONUNBUFFERED=1

export DJANGO_TESTS_DIR="django_tests_dir"
sudo mkdir -p $DJANGO_TESTS_DIR
sudo chown -R $USER:$USER django_tests_dir

pip3 install -e .
pip3 install -r requirements/gaussdb.txt

if [ ! -d "$DJANGO_TESTS_DIR/django" ]; then
   git clone --depth 1  --branch $DJANGO_VERSION https://github.com/HuaweiCloudDeveloper/django.git $DJANGO_TESTS_DIR/django
   if [ $? -ne 0 ]; then
      echo "ERROR: git clone failed"
      exit 1
   fi
fi

cp gaussdb_settings.py $DJANGO_TESTS_DIR/django/gaussdb_settings.py
cp gaussdb_settings.py $DJANGO_TESTS_DIR/django/tests/gaussdb_settings.py

pip3 install -e "$DJANGO_TESTS_DIR/django"
pip3 install -r "$DJANGO_TESTS_DIR/django/tests/requirements/py3.txt"

EXIT_STATUS=0
# Runs the tests with a concurrency of 1, meaning tests are executed sequentially rather than in parallel. 
# This ensures compatibility with databases like GaussDB or openGauss that do not allow cloning the same template database concurrently, preventing errors when creating test databases.
for DJANGO_TEST_APP in $DJANGO_TEST_APPS; do
   python3 "$DJANGO_TESTS_DIR/django/tests/runtests.py" "$DJANGO_TEST_APP" \
      --noinput --settings gaussdb_settings --parallel=1 || EXIT_STATUS=$?
done
exit $EXIT_STATUS
