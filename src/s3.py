import boto
import __main__
import logging

from boto.s3.key import Key

logger = logging.getLogger(__main__.__name__)

class S3(object):

    def __init__(self, bucket, region="us-east-1"):
        """Setup the S3 storage backend with the bucket we will use and
           optional region."""
        self.conn = boto.connect_s3()
        self.bucket = bucket

        b = self.conn.lookup(self.bucket)
        if b is None:
            # Create the bucket if it doesn't exist
            self.conn.create_bucket(self.bucket)

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

        k = Key(self.__b)
        k.key = dst
        k.set_contents_from_string(data)

    def delete(self, src):
        """Delete the object in S3 referenced by the key name src."""

        k = Key(self.__b)
        k.key = src
        k.delete()
