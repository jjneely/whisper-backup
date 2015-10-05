#!/usr/bin/env python
#
#   Copyright 2014 42 Lines, Inc.
#   Original Author: Jack Neely <jjneely@42lines.net>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import __main__
import logging

logger = logging.getLogger(__main__.__name__)

class NoOP(object):

    def __init__(self, bucket, noop):
        """Setup the S3 storage backend with the bucket we will use."""
        self.bucket = bucket
        self.noop = noop

    def list(self, prefix=""):
        """Return all keys in this bucket."""

        logger.debug("Call to list('%s') under no-op." % prefix)
        return []

    def get(self, src):
        """Return the contents of src from S3 as a string."""

        logger.debug("Call to get('%s') under no-op." % src)
        return None

    def put(self, dst, data):
        """Store the contents of the string data at a key named by dst
           in S3."""

        logger.debug("Call to put('%s') under no-op." % dst)

    def delete(self, src):
        """Delete the object in S3 referenced by the key name src."""

        logger.debug("Call to delete('%s') under no-op." % src)
