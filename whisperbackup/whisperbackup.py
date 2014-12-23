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

import sys
import os
import os.path
import logging
import fcntl
import gzip
import hashlib
import datetime
import time
import tempfile
import shutil

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


def toPath(prefix, metric):
    """Translate the metric key name in metric to its OS path location
       rooted under prefix."""

    m = metric.replace(".", "/") + ".wsp"
    return os.path.join(prefix, m)


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
    if script.args[1].lower() == "swift":
        import swift
        return swift.Swift(script.options.bucket)

    logger.error("Invalid storage backend, must be 'swift', 's3', or 'noop'")
    sys.exit(1)


def utc():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")


def backup(script):
    for k, p in listMetrics(script.options.prefix, script.options.metrics):
        logger.info("Backup: Processing %s ..." % k)
        # We acquire a file lock using the same locks whisper uses.  flock()
        # exclusive locks are cleared when the file handle is closed.  This
        # is the same practice that the whisper code uses.
        logger.debug("Locking file...")
        with open(p, "rb") as fh:
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
                # We purposely do not check retention in this case
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
        while len(knownBackups) + 1 > script.options.retention:
             # The oldest (and not current) backup
            i = knownBackups[0].replace(".sha1", "")
            logger.info("Removing old backup: %s" % i+".wsp.gz")
            try:
                script.store.delete("%s.sha1" % i)
                script.store.delete("%s.wsp.gz" % i)
            except Exception as e:
                # On an error here we want to leave files alone
                logger.warning("Exception during delete: %s" % str(e))

            del knownBackups[0]


def findBackup(script, objs, date):
    """Return the UTC ISO 8601 timestamp embedded in the given list of file
       objs that is the last timestamp before date.  Where data is a
       ISO 8601 string."""

    timestamps = []
    for i in objs:
        i = i[i.find("/")+1:]
        i = i[:i.find(".")]
        # XXX: Should probably actually parse the tz here
        timestamps.append(datetime.datetime.strptime(i, "%Y-%m-%dT%H:%M:%S+00:00"))

    refDate = datetime.datetime.strptime(script.options.date, "%Y-%m-%dT%H:%M:%S+00:00")
    timestamps.sort()
    timestamps.reverse()
    for i in timestamps:
        if refDate > i:
            return i.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    logger.warning("XXX: I shouldn't have found myself here")
    return None


def heal(script, metric, data):
    """Heal the metric in metric with the WSP data stored as a string
       in data."""

    path = toPath(script.options.prefix, metric)
    error = False

    # Make a tmp file
    fd, filename = tempfile.mkstemp(prefix="whisper-backup")
    fd = os.fdopen(fd, "wb")
    fd.write(data)
    fd.close()

    # Figure out what to do
    if os.path.exists(path):
        logger.debug("Healing existing whisper file: %s" % path)
        try:
            fill_archives(filename, path, time.time())
        except Exception as e:
            logger.warning("Exception during heal of %s will overwrite." % path)
            logger.warning(str(e))
            error = True

    # Last ditch effort, we just copy the file in place
    if error or not os.path.exists(path):
        logger.debug("Copying restored DB file into place")
        try:
            os.makedirs(os.path.dirname(path))
        except os.error:
            # Directory exists
            pass

        shutil.copyfile(filename, path)

    os.unlink(filename)


def restore(script):
    metrics = {}  # What metrics do we restore? O(1) lookups please

    # Build a list of metrics to restore from our object store and globbing
    for i in script.store.list():
        # The SHA1 is my canary/flag, we look for it
        if i.endswith(".sha1"):
            # The metric name is everything before the first /
            m = i[:i.find("/")]
            if fnmatch(m, script.options.metrics):
                if m not in metrics:
                    metrics[m] = None

    # For each metric, find the date we want
    for i in metrics.keys():
        objs = script.store.list("%s/" % i)
        d = findBackup(script, objs, script.options.date)
        logger.info("Restoring %s from timestamp %s" % (i, d))

        blobgz  = script.store.get("%s/%s.wsp.gz" % (i, d))
        blobSHA = script.store.get("%s/%s.sha1" % (i, d))

        if blobgz is None:
            logger.warning("Missing file in object store: %s/%s.wsp.gz" % (i, d))
            logger.warning("Skipping...")
            continue

        # Decompress
        blobgz = StringIO(blobgz)
        fd = gzip.GzipFile(fileobj=blobgz, mode="rb")
        blob = fd.read()
        fd.close()

        # Verify
        if blobSHA is None:
            logger.warning("Missing SHA1 checksum file...no verification")
        else:
            if hashlib.sha1(blob).hexdigest() != blobSHA:
                logger.warning("Backup does NOT verify, skipping metric %s" \
                               % i)
                continue

        heal(script, i, blob)

        # Clean up
        del blob
        blobgz.close()



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
    options.append(make_option("-c", "--date", type="string",
        default=utc(),
        help="String in ISO-8601 date format. The last backup before this date will be used during the restore.  Default is now or %s." % utc()))

    script = CronScript(usage=usage, options=options)

    if len(script.args) == 0:
        logger.info("whisper-backup.py - A Python script for backing up whisper " \
                    "database trees as used with Graphite")
        logger.info("Copyright 2014 42 Lines, Inc.")
        logger.info("Original Author: Jack Neely <jjneely@42lines.net>")
        logger.info("See the README for help or use the --help option.")
        sys.exit(1)

    if script.args[0] == "backup":
        with script:
            script.store = storageBackend(script)
            backup(script)
    elif script.args[0] == "restore":
        with script:
            script.store = storageBackend(script)
            restore(script)
    elif script.args[0] == "list":
        script.store = storageBackend(script)
        listbackups(script)
    else:
        logger.error("Command %s unknown.  Must be one of backup, restore, " \
                     "or list." % script.args[0])
        sys.exit(1)


if __name__ == "__main__":
    main()
