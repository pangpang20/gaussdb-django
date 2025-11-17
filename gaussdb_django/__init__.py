"""
GaussDB Django dialect - initialization module.
This module incorporates code from the Django project, which is
licensed under the three-clause BSD license.
Copyright (c) Django Software Foundation and individual contributors.
All rights reserved.

This derivative work is licensed under the same BSD license.
Copyright (c) 2025, HuaweiCloudDeveloper
All rights reserved.

For more information about Django's license, see the LICENSE file in the
root directory of this distribution.
"""

from .base import DatabaseWrapper

__all__ = ["DatabaseWrapper"]
