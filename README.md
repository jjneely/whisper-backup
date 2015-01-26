whisper-backup
===============

I needed a handy way to backup my Graphite cluster to reliable storage such as
Amazon S3 or OpenStack Swift.  Also, the ability to restore that data in
a sane away.  Goals:

* Compress WSP data.  Space is cash and they compress well.
* Support storing multiple backups of the same WSP DB over a retention
  period.
* Be able to restore and backup all or part of an existing tree of metrics.
* Don't waste space on duplicate WSP files.
* Verify restored data.
* Allow for manual restores if needed, we simply store Gzip versions of the
  WSP files in our storage backend.
* Support multiple storage backends.
* Use flock() (the same locking method that Whisper uses) to lock each DB
  file before uploading it.  This ensures we have a copy that wasn't in the
  middle of a file update procedure.  You have your carbon-cache daemons
  set to use locking, right?
* On restore, if the WSP file already exists just backfill in the data
  rather than overwrite it.
* File space for temp file copies is limited and is definitely not
  large enough to fit an entire backup set into.
* Use multiprocessing to handle large backup sets faster.

Usage
-----

I decided not to design this to store multiple servers worth of WSP files in
a single bucket/container of the storage service.  For large clusters this
could be millions of files which may cause slowness with the API and other
issues.  So if you have multiple servers you should set each machine to backup
to its own bucket/container.

```
$ python whisperbackup.py --help
Usage: whisperbackup.py [options] backup|restore|list swift|s3 [storage args]

Options:
  -p PREFIX, --prefix=PREFIX
                        Root of where the whisper files live or will be
                        restored to, default /opt/graphite/storage/whisper
  -f PROCESSES, --processes=PROCESSES
                        Number of worker processes to spawn, default 4
  -r RETENTION, --retention=RETENTION
                        Number of unique backups to retain for each whisper
                        file, default 5
  -b BUCKET, --bucket=BUCKET
                        The AWS S3 bucket name or Swift container to use,
                        default graphite-backups
  -m METRICS, --metrics=METRICS
                        Glob pattern of metric names to backup or restore,
                        default *
  -c DATE, --date=DATE  String in ISO-8601 date format. The last backup before
                        this date will be used during the restore.  Default is
                        now or 2015-01-26T15:41:55+00:00.
  -d, --debug           Minimum log level of DEBUG
  -q, --quiet           Only WARN and above to stdout
  --nolog               Do not log to LOGFILE
  --logfile=LOGFILE     File to log to, default /var/log/whisperbackup.py
  --nolock              Do not use a lockfile
  --lockfile=LOCKFILE   Lock file, default /var/tmp/whisperbackup.py
  --locktimeout=LOCKTIMEOUT
                        Lock timeout in seconds, default 90
  --splay=SPLAY         Sleep a random time between 0 and N seconds before
                        starting, default 0
  -h, --help            show this help message and exit
```

Requirements
------------

Required python packages and the versions of which I've tested with.

* whisper >= 0.9.12
* carbon >= 0.9.12
* carbonate >= 0.2.1
* lockfile

For AWS S3 support:

* boto

For OpenStack Swift support:

* python-swiftclient

Assumptions
-----------

* We assume that each WSP file will fit in memory.

To Do
-----

* We use multiprocess.Pool for backups, but restores are still single process
