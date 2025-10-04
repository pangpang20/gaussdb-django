#!/bin/bash
# Copyright (c) 2025, HuaweiCloudDeveloper
# Licensed under the BSD 3-Clause License.
# See LICENSE file in the project root for full license information.

set -x pipefail

# Disable buffering, so that the logs stream through.
export PYTHONUNBUFFERED=1

export DJANGO_TESTS_DIR="django_tests_dir"
mkdir -p $DJANGO_TESTS_DIR

pip3 install -e .
git clone --depth 1  --branch $DJANGO_VERSION git@github.com:pangpang20/django.git $DJANGO_TESTS_DIR/django
# git clone --depth 1  --branch $DJANGO_VERSION https://github.com/django/django.git $DJANGO_TESTS_DIR/django
cp tidb_settings.py $DJANGO_TESTS_DIR/django/tidb_settings.py
cp tidb_settings.py $DJANGO_TESTS_DIR/django/tests/tidb_settings.py
cp -rT ./tests/tidb $DJANGO_TESTS_DIR/django/tests/tidb
cp -rT ./tests/tidb_field_defaults $DJANGO_TESTS_DIR/django/tests/tidb_field_defaults

cd $DJANGO_TESTS_DIR/django && pip3 install -e . && pip3 install -r tests/requirements/py3.txt && pip3 install -r tests/requirements/mysql.txt; cd ../../
cd $DJANGO_TESTS_DIR/django/tests

EXIT_STATUS=0
for DJANGO_TEST_APP in $DJANGO_TEST_APPS
do
   python3 runtests.py $DJANGO_TEST_APP --noinput --settings tidb_settings || EXIT_STATUS=$?
   if [[ $EXIT_STATUS -ne 0 ]]; then
      exit $EXIT_STATUS
   fi
done
exit $EXIT_STATUS
