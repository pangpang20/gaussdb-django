#!/usr/bin/env python3

# Copyright (c) 2025, HuaweiCloudDeveloper
# Licensed under the BSD 3-Clause License.
# See LICENSE file in the project root for full license information.

import os
import time

start_time = time.time()

with open("django_test_apps.txt", "r") as file:
    all_apps = file.read().split("\n")

print("test apps: ", all_apps)

if not all_apps:
    exit()

exitcode = os.WEXITSTATUS(
    os.system(
        """DJANGO_TEST_APPS="{apps}" bash ./django_test_suite.sh""".format(
            apps=" ".join(all_apps)
        )
    )
)

end_time = time.time()
elapsed_time = end_time - start_time

print(f"\nTotal elapsed time: {elapsed_time:.2f} seconds")

exit(exitcode)
