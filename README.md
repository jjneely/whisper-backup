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

* python-swift

Assumptions
-----------

* We assume that each WSP file will fit in memory
* We compress WSP files in memory and forget the source
* We flock() each WSP during the checksum, and reading process
