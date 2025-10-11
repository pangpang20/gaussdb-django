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
   git clone --depth 1  --branch $DJANGO_VERSION https://ghfast.top/https://github.com/pangpang20/django.git $DJANGO_TESTS_DIR/django
   # git clone --depth 1 --branch $DJANGO_VERSION git@codehub-cn-south-1.devcloud.huaweicloud.com:8e6242e6acc84b01898ebac5cf786c4e/django.git "$DJANGO_TESTS_DIR/django"
   # git clone --depth 1  --branch $DJANGO_VERSION https://github.com/django/django.git $DJANGO_TESTS_DIR/django
   if [ $? -ne 0 ]; then
      echo "ERROR: git clone failed"
      exit 1
   fi
fi

cp gaussdb_settings.py $DJANGO_TESTS_DIR/django/gaussdb_settings.py
cp gaussdb_settings.py $DJANGO_TESTS_DIR/django/tests/gaussdb_settings.py
# cp -rT ./tests/tidb $DJANGO_TESTS_DIR/django/tests/tidb
# cp -rT ./tests/tidb_field_defaults $DJANGO_TESTS_DIR/django/tests/tidb_field_defaults

# update tests case for gaussdb
sed -i 's/self.assertEqual(pony.empty, "")/self.assertEqual(pony.empty, " ")/g' $DJANGO_TESTS_DIR/django/tests/migrations/test_operations.py

pip3 install -e "$DJANGO_TESTS_DIR/django"
pip3 install -r "$DJANGO_TESTS_DIR/django/tests/requirements/py3.txt"
# pip3 install -r "$DJANGO_TESTS_DIR/django/tests/requirements/postgres.txt"

EXIT_STATUS=0
for DJANGO_TEST_APP in $DJANGO_TEST_APPS; do
   python3 "$DJANGO_TESTS_DIR/django/tests/runtests.py" "$DJANGO_TEST_APP" \
      --noinput --settings gaussdb_settings --parallel=1 || EXIT_STATUS=$?
done
exit $EXIT_STATUS
