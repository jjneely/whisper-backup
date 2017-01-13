#!/usr/bin/env python
#
#
#   Original Author: Charles Dunbar <ccdunbar@gmail.com>
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
import glob
import logging
import os

logger = logging.getLogger(__main__.__name__)

class Disk(object):

    def __init__(self, bucket, noop=False):

        self.bucket = bucket
        self.noop = noop

    def list(self, prefix="*/"):
        """ Return all keys in this bucket."""

        list_rep = glob.glob(self.bucket + "/" + prefix + "/*")
        for i in list_rep:
            # Remove preceding bucket name and potential leading slash from returned key value
            i =  i.replace(self.bucket, "")
            if i[0] == '/': i = i[1:]
            yield i

    def get(self, src):
        """Return the contents of src from disk as a string."""

        if not os.path.exists(os.path.dirname(self.bucket + "/" + src)):
            return None
        k = ""
        try:
            with open(self.bucket + "/" + src, 'rb') as f:
                k = f.read()
        except Exception as e:
            logger.warning("Exception during get: %s" % str(e))
        return k

    def put(self, dst, data):
        """Store the contents of the string data at a key named by dst
           on disk."""

        if self.noop:
            logger.info("No-Op Put: %s" % dst)
        else:
            filename = self.bucket + "/" + dst
            if not os.path.exists(os.path.dirname(filename)):
                    os.makedirs(os.path.dirname(filename))
            try:
                with open(self.bucket + "/" + dst, 'wb') as f:
                    f.write(data)
            except Exception as e:
                logger.warning("Exception during put: %s" % str(e))


    def delete(self, src):
        """Delete the object on disk referenced by the key name src."""

        if self.noop:
            logger.info("No-Op Delete: %s" % self.bucket + "/" + src)
        else:
            logger.info("Trying to delete %s" % self.bucket + "/" + src)
            os.remove(self.bucket + "/" + src)
