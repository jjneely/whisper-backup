import __main__
import logging

logger = logging.getLogger(__main__.__name__)

class NoOP(object):

    def __init__(self, bucket):
        """Setup the S3 storage backend with the bucket we will use and
           optional region."""
        self.bucket = bucket

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
