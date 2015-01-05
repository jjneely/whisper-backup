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
  large enough to fit an entire backup into.

Usage
-----

I decided not to make room to store multiple servers worth of WSP files in
a single bucket/container of the storage service.  For large clusters this
could be millions of files which may cause slowness with the API and other
issues.  So if you have multiple servers you should set each machine to backup
to its own bucket/container.

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
