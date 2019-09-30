whisper-backup
===============

I needed a handy way to backup my Graphite cluster to reliable storage such as
Amazon S3, Google Cloud Storage, or OpenStack Swift.  Also, the ability to
restore that data in a sane away.  Hence, I wrote `whisper-backup`.

Examples
--------

Backup:
```
$ whisper-backup --logfile /opt/graphite/storage/log/whisper-backup/whisper-backup.log \
        --bucket $(hostname -s) \
        --retention 5 \
        --quiet \
        backup swift
```

Restore:
```
$ whisper-backup --logfile /opt/graphite/storage/log/whisper-backup/whisper-backup.log \
        --bucket $(hostname -s) \
        --prefix /data/tmp \
        restore swift
```

Goals
-----

* Compress WSP data.  Space is cash and they compress well.  Gzip and Snappy
  compression is supported.
* Support storing multiple backups of the same WSP DB over a retention
  period.
* Be able to restore and backup all or part of an existing tree of metrics.
* Don't waste space on duplicate WSP files.
* Verify restored data.
* Allow for manual restores if needed, we simply store Gzip/Snappy versions of
  the WSP files in our storage backend.
* Support multiple storage backends.
* Use `flock()` (the same locking method that Whisper uses) to lock each DB
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
Usage: whisperbackup.py [options] backup|restore|purge|list disk|gcs|noop|s3|swift [storage args]

Options:
  -p PREFIX, --prefix=PREFIX
                        Root of where the whisper files live or will be
                        restored to, default /opt/graphite/storage/whisper
  -f PROCESSES, --processes=PROCESSES
                        Number of worker processes to spawn, default 4
  -r RETENTION, --retention=RETENTION
                        Number of unique backups to retain for each whisper
                        file, default 5
  -x PURGE, --purge=PURGE
                        Days to keep unknown Whisper file backups, -1
                        disables, default 45
  -n, --noop            Do not modify the object store, default False
  -b BUCKET, --bucket=BUCKET
                        The AWS S3 bucket name or Swift container to use,
                        default graphite-backups
  -m METRICS, --metrics=METRICS
                        Glob pattern of metric names to backup or restore,
                        default *
  -c DATE, --date=DATE  String in ISO-8601 date format. The last backup before
                        this date will be used during the restore.  Default is
                        now or 2019-09-30T17:52:51+00:00.
  -a ALGORITHM, --algorithm=ALGORITHM
                        Compression format to use based on installed Python
                        modules.  Choices: gz, sz
  --storage-path=STORAGE_PATH
                        Path in the bucket to store the backup, default
  -d, --debug           Minimum log level of DEBUG
  -q, --quiet           Only WARN and above to stdout
  --nolog               Do not log to LOGFILE
  --logfile=LOGFILE     File to log to, default /var/log/whisperbackup.py.log
  --syslog              Log to syslog instead of a file
  --nolock              Do not use a lockfile
  --lockfile=LOCKFILE   Lock file, default /var/lock/whisperbackup.py
  --nostamp             Do not use a success stamp file
  --stampfile=STAMPFILE
                        Success stamp file, default
                        /var/tmp/whisperbackup.py.success
  --locktimeout=LOCKTIMEOUT
                        Lock timeout in seconds, default 90
  --splay=SPLAY         Sleep a random time between 0 and N seconds before
                        starting, default 0
  -h, --help            show this help message and exit

```

Notes:
* Purge removes Whisper backups in the datastore for Whisper files not
  presently on the server.  Such as deleted or moved Whisper files.  A setting
  of 0 will immediately purge backups for metrics not on the local disk,
  -1 will disable purge.

Compression Algorithms and Notes
--------------------------------

Historically this tool has compressed Whisper files with Python's gzip
implementation.  This was done so that the compressed files could be manually
pulled and restored if needed.  All the compressed Whisper files were readable
by the `gunzip` utility.

Gzip offers reasonable compression, but is quite slow.  If a Graphite cluster
has many Whisper files, this backup utility would take hours or days to
complete a backup cycle due to the time spend gzipping each Whisper file.
Due to this whisper-backup now supports multiple compression algorithms.

Each supported algorithm is identified by its file name suffix:

* Gzip (default): `gz`
* Google Snappy: `sz`

On a test Graphite data node with only a few thousand metrics, using Gzip
made a runtime of 73+ minutes to complete a backup cycle.  With Snappy that
dropped to 8 minutes.

To decompress a `*.sz` file manually you can use the python-snappy module
that whisper-backup uses:

    python -m snappy -d compressed.wsp.sz cleartext.wsp

You can compress as well with the `-c` option rather than `-d`.  Any tool
that supports the [Snappy Framing Format][1] should be able to decompress
these files.

Requirements
------------

Required Python packages and the versions of which I've tested with.

* whisper >= 0.9.12
* carbon >= 0.9.12
* lockfile

Storage Backends and Requirements
---------------------------------

### Google Snappy Compression

Installing the `snappy` Python module will enable support in whisper-backup.

    $ pip install snappy

Some distributions may package this as `python-snappy`.

### AWS S3 Backend

The `boto` package must be installed.

    $ pip install boto

Make sure your AWS credentials are set so that Boto will find them.  This is
normally setting the environment variables `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY`.

### OpenStack Swift Backend

Make sure the `swiftclient` Python package is installed that is version 3.0.0
or better.

    $ pip install swiftclient

Set the environment variables `ST_AUTH`, `ST_USER`, and `ST_KEY` for
authentication to your Swift endpoint.

### Google Cloud Storage Backend

The `google-cloud-storage` Python package must be installed.

    $ pip install google-cloud-storage

This uses the Google's default application credentials system to locate
credentials to use.  If this is running in GCP the service account that
the GCE VMs running this code use simply needs the correct access to GCS
buckets.  Otherwise the `GOOGLE_APPLICATION_CREDENTIALS` environment variable
should be set to reference the on disk file of GCP credentials.

Contributions
-------------

PRs are welcome.

To Do
-----

* We use multiprocess.Pool for backups, but restores are still single process
* Purge bug:  If a metric has been idle for 45 days
  then the backup date on that file in the object store hasn't changed.  So
  once that metric is removed from local disk it will be immediately removed
  from the object store rather than 45 days after it was removed from local
  disk.
* Signal handler or Control-C to terminate all processes.

[1]: https://github.com/google/snappy/blob/master/framing_format.txt
