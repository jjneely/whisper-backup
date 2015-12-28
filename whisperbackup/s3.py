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

import boto
import __main__
import logging

from boto.s3.key import Key

logger = logging.getLogger(__main__.__name__)

class S3(object):

    def __init__(self, bucket, region="us-east-1", noop=False):
        """Setup the S3 storage backend with the bucket we will use and
           optional region."""
        self.conn = boto.s3.connect_to_region(region)
        self.bucket = bucket
        self.noop = noop

        b = self.conn.lookup(self.bucket)
        if not noop and b is None:
            # Create the bucket if it doesn't exist
            self.conn.create_bucket(self.bucket, location=region)

        self.__b = self.conn.get_bucket(self.bucket)

    def list(self, prefix=""):
        """Return all keys in this bucket."""
        for i in self.__b.list(prefix):
            yield i.key

    def get(self, src):
        """Return the contents of src from S3 as a string."""
        if self.__b.get_key(src) is None:
            return None

        k = Key(self.__b)
        k.key = src
        return k.get_contents_as_string()

    def put(self, dst, data):
        """Store the contents of the string data at a key named by dst
           in S3."""

        if self.noop:
            logger.info("No-Op Put: %s" % dst)
        else:
            k = Key(self.__b)
            k.key = dst
            k.set_contents_from_string(data)

    def delete(self, src):
        """Delete the object in S3 referenced by the key name src."""

        if self.noop:
            logger.info("No-Op Delete: %s" % src)
        else:
            k = Key(self.__b)
            k.key = src
            k.delete()
