import sys
import os
import os.path
import logging
import fcntl
import gzip
import hashlib
import datetime

from optparse import make_option
from fnmatch import fnmatch
from StringIO import StringIO

from carbonate.fill import fill_archives
from pycronscript import CronScript

logger = logging.getLogger(__name__)

def listMetrics(storage_dir, glob):
    storage_dir = storage_dir.rstrip(os.sep)

    for root, dirnames, filenames in os.walk(storage_dir):
        for filename in filenames:
            if filename.endswith(".wsp"):
                root_path = root[len(storage_dir) + 1:]
                m_path = os.path.join(root_path, filename)
                m_name, m_ext = os.path.splitext(m_path)
                m_name = m_name.replace('/', '.')
                if glob == "*" or fnmatch(m_name, glob):
                    # We use globbing on the metric name, not the path
                    yield m_name, os.path.join(root, filename)


def storageBackend(script):
    if len(script.args) <= 1:
        logger.error("Storage backend must be specified, either 'swift' or 's3'")
        sys.exit(1)
    if script.args[1].lower() == "noop":
        import noop
        return noop.NoOP(script.options.bucket)
    if script.args[1].lower() == "s3":
        import s3
        if len(script.args) > 2:
            region = script.args[2]
        else:
            region = "us-east-1"
        return s3.S3(script.options.bucket, region)
    #if script.args[1].lower() == "swift":
    #    return None

    logger.error("Invalid storage backend, must be 'swift' or 's3'")
    sys.exit(1)


def utc():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")


def backup(script):
    for k, p in listMetrics(script.options.prefix, script.options.metrics):
        logger.info("Backup: Processing %s ..." % k)
        # We acquire a file lock using the same locks whisper uses.  flock()
        # exclusive locks are cleared when the file handle is closed.  This
        # is the same practice that the whisper code uses.
        logger.debug("Locking file...")
        with open(p, "r+b") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)  # May block
            blob = fh.read()
            timestamp = utc()

        # SHA1 hash...have we seen this metric DB file before?
        logger.debug("Calculating hash and searching data store...")
        blobSHA = hashlib.sha1(blob).hexdigest()
        knownBackups = []
        for i in script.store.list(k+"/"):
            if i.endswith(".sha1"):
                knownBackups.append(i)

        knownBackups.sort()
        if len(knownBackups) > 0:
            i = knownBackups[-1] # The last known backup
            logger.debug("Examining %s from data store..." % i)
            if script.store.get(i) == blobSHA:
                logger.info("Metric DB %s is unchanged from last backup, " \
                            "skipping." % k)
                continue

        # We're going to backup this file, compress it as a normal .gz
        # file so that it can be restored manually if needed
        logger.debug("Compressing data...")
        blobgz = StringIO()
        fd = gzip.GzipFile(fileobj=blobgz, mode="wb")
        fd.write(blob)
        fd.close()

        # Grab our timestamp and assemble final upstream key location
        remote = "%s/%s" % (k, timestamp)
        logger.debug("Uploading payload...")
        script.store.put("%s/%s.wsp.gz" % (k, timestamp), blobgz.getvalue())
        script.store.put("%s/%s.sha1" % (k, timestamp), blobSHA)

        # Free Memory
        blobgz.close()
        del blob

        # Handle our retention polity, we keep at most X backups
        if len(knownBackups) + 1 > script.options.retention:
            i = knownBackups[0] # The oldest (and not current) backup
            i.repace(".sha1", "")
            logger.info("Removing old backup: %s" % i+".wsp.gz")
            try:
                script.store.delete("%s.sha1")
                script.store.delete("%s.wsp.gz")
            except:
                # On an error here we want to leave files alone
                logger.warning("Exception during delete: %s" % str(e))


def restore(script):
    pass

def listbackups(script):
    c = 0
    # This list is sorted, we will use that to our advantage
    key = None
    for i in script.store.list():
        if i.endswith(".wsp.gz"):
            if key is None or key != i:
                key = i
                print key[:-33]

            print "\tDate: %s" % key[len(key[:-32]):-7]
            c += 1

    print
    if c == 0:
        print "No backups found."
    else:
        print "%s compressed whisper databases found." % c


def main():
    usage = "%prog [options] backup|restore|list swift|s3 [storage args]"
    options = []

    options.append(make_option("-p", "--prefix", type="string",
        default="/opt/graphite/storage/whisper",
        help="Root of where the whisper files live or will be restored to, default %default"))
    options.append(make_option("-r", "--retention", type="int",
        default=5,
        help="Number of unique backups to retain for each whisper file, default %default"))
    options.append(make_option("-b", "--bucket", type="string",
        default="graphite-backups",
        help="The AWS S3 bucket name or Swift container to use, default %default"))
    options.append(make_option("-m", "--metrics", type="string",
        default="*",
        help="Glob pattern of metric names to backup or restore, default %default"))

    script = CronScript(usage=usage, options=options)
    script.store = storageBackend(script)

    if script.args[0] == "backup":
        backup(script)
    elif script.args[0] == "restore":
        restore(script)
    elif script.args[0] == "list":
        listbackups(script)
    else:
        logger.error("Command %s unknown.  Must be one of backup, restore, " \
                     "or list." % script.args[0])
        sys.exit(1)


if __name__ == "__main__":
    main()
