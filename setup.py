#!/usr/bin/env python
#
# Copyright 2014 42Lines, Inc.
# Original Author: Jack Neely <jjneely@42lines.net>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


setup_args = {
    "name": "whisper-backup",
    "version": "0.0.2",
    "platforms": ["any"],
    "description": "Backup whisper DB files into S3 or Swift",
    "long_description": """\
Whisper-backup stores compressed WSP files in Amazon S3 or OpenStack Swift
from a Graphite setup.  It can backup and restore selected metric globs,
has a retention policy setting, and does not stage backups on the local
server.
""",
    "author": "Jack Neely",
    "author_email": "jjneely@42lines.net",
    "maintainer": "Jack Neely",
    "maintainer_email": "jjneely@42lines.net",
    "url": 'https://github.com/jjneely/whisper-backup',
    "license": "Apache Software License",
    "packages": ["whisperbackup"],
    "install_requires": ['lockfile', 'carbonate', 'whisper'],
    "classifiers": [
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: System :: Systems Administration"
        ],
    "entry_points": {
        "console_scripts": [
            "whisper-backup = whisperbackup.whisperbackup:main"
        ]
    }
}

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(**setup_args)
