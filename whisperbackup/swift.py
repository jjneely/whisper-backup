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
import os
import sys

from swiftclient.client import Connection
from swiftclient.exceptions import ClientException

logger = logging.getLogger(__main__.__name__)

class Swift(object):

    def __init__(self, bucket, noop):
        """Setup the S3 storage backend with the bucket we will use."""

        # This is our Swift container
        self.bucket = bucket
        self.noop = noop

        # We assume your environment variables are set correctly just like
        # you would for the swift command line util
        try:
            self.conn = Connection(authurl=os.environ["ST_AUTH"],
                               user=os.environ["ST_USER"],
                               key=os.environ["ST_KEY"])
        except KeyError:
            logger.warning("Missing environment variables for Swift authentication")
            logger.warning("Bailing...")
            sys.exit(1)

        headers, objs =  self.conn.get_account(self.bucket)
        for i in objs:
            logger.debug("Searching for bucket %s == %s" % (self.bucket, i))
        if not noop and self.bucket not in objs:
            self.conn.put_container(self.bucket)


    def list(self, prefix=None):
        """Return all keys in this bucket."""

        headers, objs = self.conn.get_container(self.bucket, prefix=prefix)
        while objs:
            # Handle paging
            i = {}
            for i in objs:
                yield i["name"]
            headers, objs = self.conn.get_container(self.bucket,
                    marker=i["name"], prefix=prefix)


    def get(self, src):
        """Return the contents of src from S3 as a string."""

        try:
            headers, obj = self.conn.get_object(self.bucket, src)
            return obj
        except ClientException:
            # Request failed....object doesn't exist
            return None


    def put(self, dst, data):
        """Store the contents of the string data at a key named by dst
           in S3."""

        if self.noop:
            logger.info("No-Op Put: %s" % dst)
        else:
            self.conn.put_object(self.bucket, dst, data)


    def delete(self, src):
        """Delete the object in S3 referenced by the key name src."""

        if self.noop:
            logger.info("No-Op Delete: %s" % src)
        else:
            self.conn.delete_object(self.bucket, src)
