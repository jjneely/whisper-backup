#!/usr/bin/env python
#
#   Copyright 2019 42 Lines, Inc.
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

from google.cloud import storage

logger = logging.getLogger(__main__.__name__)

# Google Cloud Storage
class GCS(object):

    def __init__(self, bucket, project="", region="us", noop=False):
        """Setup the GCS storage backend with the bucket we will use and
           optional region."""
        if project == "":
            self.client = storage.Client()
        else:
            self.client = storage.Client(project)

        self.noop = noop

        self.bucket = storage.Bucket(self.client, bucket)
        self.bucket.location = region
        self.bucket.storage_class = "STANDARD"

        # Create the bucket if it doesn't exist
        if not self.bucket.exists():
            if not noop:
                self.bucket.create()
            else:
                logger.info("No-Op: Create bucket: %s" % bucket)

    def list(self, prefix=""):
        """Return all keys in this bucket."""
        for i in self.client.list_blobs(self.bucket, prefix=prefix):
            yield i.name

    def get(self, src):
        """Return the contents of src from this bucket as a string."""
        obj = storage.blob.Blob(src, self.bucket)
        if not obj.exists():
            return None

        return obj.download_as_string()

    def put(self, dst, data):
        """Store the contents of the string data at a key named by dst
           in GCS."""

        if self.noop:
            logger.info("No-Op Put: %s" % dst)
        else:
            obj = storage.blob.Blob(dst, self.bucket)
            obj.upload_from_string(data, content_type="application/octet-stream")

    def delete(self, src):
        """Delete the object in GCP referenced by the key name src."""

        if self.noop:
            logger.info("No-Op Delete: %s" % src)
        else:
            obj = storage.blob.Blob(dst, self.bucket)
            obj.delete()

