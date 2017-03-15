#!/usr/bin/env python
#
#   Copyright 2014-2017 42 Lines, Inc.
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

from multiprocessing import Pool
from optparse import make_option
from fnmatch import fnmatch
from StringIO import StringIO

from fill import fill_archives
from pycronscript import CronScript

import __main__

logger = logging.getLogger(__main__.__name__)

def listMetrics(storage_dir, storage_path, glob):
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
                    yield storage_path + m_name, os.path.join(root, filename)


def toPath(prefix, metric):
    """Translate the metric key name in metric to its OS path location
       rooted under prefix."""

    m = metric.replace(".", "/") + ".wsp"
    return os.path.join(prefix, m)


def storageBackend(script):
    if len(script.args) <= 1:
        logger.error("Storage backend must be specified, either 'swift', 's3', 'noop', or 'disk'")
        sys.exit(1)
    if script.args[1].lower() == "disk":
        import disk
        return disk.Disk(script.options.bucket, script.options.noop)
    if script.args[1].lower() == "noop":
        import noop
        return noop.NoOP(script.options.bucket, script.options.noop)
    if script.args[1].lower() == "s3":
        import s3
        if len(script.args) > 2:
            region = script.args[2]
        else:
            region = "us-east-1"
        return s3.S3(script.options.bucket, region, script.options.noop)
    if script.args[1].lower() == "swift":
        import swift
        return swift.Swift(script.options.bucket, script.options.noop)

    logger.error("Invalid storage backend, must be 'swift', 's3', 'noop', or 'disk'")
    sys.exit(1)


def utc():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")


def backup(script):
    # I want to modify these variables in a sub-function, this is the
    # only thing about python 2.x that makes me scream.
    data = {}
    data['complete'] = 0
    data['length'] = 0

    def init(script):
        # The script object isn't pickle-able
        globals()['script'] = script

    def cb(result):
        # Do some progress tracking when jobs complete
        data['complete'] = data['complete'] + 1
        if  data['complete'] % 5 == 0:
            # Some rate limit on logging
            logger.info("Progress: %s/%s or %f%%" \
                    % (data['complete'], data['length'],
                       100 * float(data['complete']) / float(data['length'])))

    logger.info("Scanning filesystem...")
    # Unroll the generator so we can calculate length
    jobs = [ (k, p) for k, p in listMetrics(script.options.prefix, script.options.storage_path, script.options.metrics) ]
    data['length'] = len(jobs)

    workers = Pool(processes=script.options.processes,
                   initializer=init, initargs=[script])
    logger.info("Starting backup...")
    for k, p in jobs:
        workers.apply_async(backupWorker, [k, p], callback=cb)

    workers.close()
    workers.join()
    logger.info("Backup complete.")

    purge(script, [ k for k, p in jobs ])


def purge(script, localMetrics):
    """Purge backups in our store that are non-existant on local disk and
       are more than purge days old as set in the command line options."""

    if script.options.purge < 0:
        # purging is disabled
        return

    logger.info("Beginning purge operation.")
    metrics = search(script)
    expireDate = datetime.datetime.utcnow() - datetime.timedelta(days=script.options.purge)
    expireStamp = expireDate.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    c = 0

    # Search through the in-store metrics
    for k, v in metrics.items():
        if k in localMetrics:
            continue
        for p in v:
            ts = p[p.find("/")+1:]
            if ts < expireStamp:
                logger.info("Purging %s @ %s" % (k, ts))
                try:
                    # Delete the WSP file first, if the delete of the SHA1
                    # causes the error, the next run will get it, rather
                    # than just leaking the WSP storage space.
                    script.store.delete("%s%s/%s.wsp.gz" % (script.options.storage_path, k, ts))
                    script.store.delete("%s%s/%s.sha1" % (script.options.storage_path, k, ts))
                except Exception as e:
                    # On an error here we want to leave files alone
                    logger.warning("Exception during delete: %s" % str(e))
                else:
                    c += 1

    logger.info("Purge complete -- %d backups removed" % c)


def backupWorker(k, p):
    # Inside this fuction/process 'script' is global
    logger.info("Backup: Processing %s ..." % k)
    # We acquire a file lock using the same locks whisper uses.  flock()
    # exclusive locks are cleared when the file handle is closed.  This
    # is the same practice that the whisper code uses.
    logger.debug("Locking file...")
    try:
        with open(p, "rb") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)  # May block
            blob = fh.read()
            timestamp = utc()
    except IOError as e:
        logger.warning("An IOError occured locking %s: %s" \
                % (k, str(e)))
        return
    except Exception as e:
        logger.error("An Unknown exception occurred, skipping metric")
        logger.error(str(e))
        return

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
            return

    # We're going to backup this file, compress it as a normal .gz
    # file so that it can be restored manually if needed
    if not script.options.noop:
        logger.debug("Compressing data...")
        blobgz = StringIO()
        fd = gzip.GzipFile(fileobj=blobgz, mode="wb")
        fd.write(blob)
        fd.close()
    else:
        logger.info("Skipping compression for noop run")

    # Grab our timestamp and assemble final upstream key location
    remote = "%s/%s" % (k, timestamp)
    logger.debug("Uploading payload...")
    try:
        script.store.put("%s/%s.wsp.gz" % (k, timestamp), blobgz.getvalue())
        script.store.put("%s/%s.sha1" % (k, timestamp), blobSHA)
    except Exception as e:
        logger.warning("Exception during upload: %s" % str(e))

    # Free Memory
    blobgz.close()
    del blob

    # Handle our retention polity, we keep at most X backups
    while len(knownBackups) + 1 > script.options.retention:
         # The oldest (and not current) backup
        i = knownBackups[0].replace(".sha1", "")
        logger.info("Removing old backup: %s" % i+".wsp.gz")
        try:
            script.store.delete("%s.wsp.gz" % i)
            script.store.delete("%s.sha1" % i)
        except Exception as e:
            # On an error here we want to leave files alone
            logger.warning("Exception during delete: %s" % str(e))

        del knownBackups[0]


def findBackup(script, objs, date):
    """Return the UTC ISO 8601 timestamp embedded in the given list of file
       objs that is the last timestamp before date.  Where date is a
       ISO 8601 string."""

    timestamps = []
    for i in objs:
        i = i[i.find("/")+1:]
        if "." in i:
            i = i[:i.find(".")]
        # So now i is just the ISO8601 timestamp
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

def search(script):
    """Return a hash such that all keys are metric names found in our
       backup store and metric names match the glob given on the command
       line.  Each value will be a list paths into the backup store of
       all present backups.  Technically, the path to the SHA1 checksum file
       but the path will not have the ".sha1" extension."""

    logger.info("Searching remote file store...")
    metrics = {}

    for i in script.store.list(prefix=script.options.storage_path):
        i = i[len(script.options.storage_path):]
        # The SHA1 is my canary/flag, we look for it
        if i.endswith(".sha1"):
            # The metric name is everything before the first /
            m = i[:i.find("/")]
            if fnmatch(m, script.options.metrics):
                metrics.setdefault(m, []).append(i[:-5])

    return metrics


def restore(script):
    # Build a list of metrics to restore from our object store and globbing
    metrics = search(script)

    # For each metric, find the date we want
    for i in metrics.keys():
        objs = metrics[i]
        d = findBackup(script, objs, script.options.date)
        logger.info("Restoring %s from timestamp %s" % (i, d))

        blobgz  = script.store.get("%s%s/%s.wsp.gz" % (script.options.storage_path,i, d))
        blobSHA = script.store.get("%s%s/%s.sha1" % (script.options.storage_path,i, d))

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
    usage = "%prog [options] backup|restore|purge|list disk|swift|s3 [storage args]"
    options = []

    options.append(make_option("-p", "--prefix", type="string",
        default="/opt/graphite/storage/whisper",
        help="Root of where the whisper files live or will be restored to, default %default"))
    options.append(make_option("-f", "--processes", type="int",
        default=4,
        help="Number of worker processes to spawn, default %default"))
    options.append(make_option("-r", "--retention", type="int",
        default=5,
        help="Number of unique backups to retain for each whisper file, default %default"))
    options.append(make_option("-x", "--purge", type="int",
        default=45,
        help="Days to keep unknown Whisper file backups, 0 disables, default %default"))
    options.append(make_option("-n", "--noop", action="store_true",
        default=False,
        help="Do not modify the object store, default %default"))
    options.append(make_option("-b", "--bucket", type="string",
        default="graphite-backups",
        help="The AWS S3 bucket name or Swift container to use, default %default"))
    options.append(make_option("-m", "--metrics", type="string",
        default="*",
        help="Glob pattern of metric names to backup or restore, default %default"))
    options.append(make_option("-c", "--date", type="string",
        default=utc(),
        help="String in ISO-8601 date format. The last backup before this date will be used during the restore.  Default is now or %s." % utc()))
    options.append(make_option("--storage-path", type="string",
        default="",
        help="Path in the bucket to store the backup, default %default"))

    script = CronScript(usage=usage, options=options)

    if len(script.args) == 0:
        logger.info("whisper-backup.py - A Python script for backing up whisper " \
                    "database trees as used with Graphite")
        logger.info("Copyright 2014 42 Lines, Inc.")
        logger.info("Original Author: Jack Neely <jjneely@42lines.net>")
        logger.info("See the README for help or use the --help option.")
        sys.exit(1)

    mode = script.args[0].lower()
    if mode == "backup":
        with script:
            # Use splay and lockfile settings
            script.store = storageBackend(script)
            backup(script)
    elif mode == "restore":
        with script:
            # Use splay and lockfile settings
            script.store = storageBackend(script)
            restore(script)
    elif mode == "purge":
        with script:
            # Use splay and lockfile settings
            script.store = storageBackend(script)
            purge(script, [k for k, p in listMetrics(script.options.prefix, script.options.storage_path, script.options.metrics)])
    elif mode == "list":
        # Splay and lockfile settings make no sense here
        script.store = storageBackend(script)
        listbackups(script)
    else:
        logger.error("Command %s unknown.  Must be one of backup, restore, " \
                     "purge, or list." % script.args[0])
        sys.exit(1)


if __name__ == "__main__":
    main()
