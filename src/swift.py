import __main__
import logging
import os
import sys

from swiftclient.client import Connection
from swiftclient.exceptions import ClientException

logger = logging.getLogger(__main__.__name__)

class Swift(object):

    def __init__(self, bucket):
        """Setup the S3 storage backend with the bucket we will use and
           optional region."""

        # This is our Swift container
        self.bucket = bucket

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
        if self.bucket not in objs:
            self.conn.put_container(self.bucket)


    def list(self, prefix=""):
        """Return all keys in this bucket."""

        if prefix == "":
            headers, objs = self.conn.get_container(self.bucket)
        else:
            headers, objs = self.conn.get_container(self.bucket, prefix=prefix)

        for i in objs:
            yield i["name"]


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

        self.conn.put_object(self.bucket, dst, data)


    def delete(self, src):
        """Delete the object in S3 referenced by the key name src."""

        self.conn.delete_object(self.bucket, src)


if __name__ == "__main__":
    s = Swift("fitbit.graphite-test")

    def show():
        for i in s.list():
            print i

    print "Should be empty"
    show()
    print
    print "Non-existent file: %s" % s.get("foobar")
    print
    print "Storing a test"
    s.put("test", "This is a test")
    print
    print "Test file contents: %s" % s.get("test")
    print
    print "Objects in bucket"
    show()
    print
    print "Deleting test file"
    s.delete("test")
    print

