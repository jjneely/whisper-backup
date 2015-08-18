''' Convenience class for writing cron scripts'''
# pylint: disable=R0903

# Copyright 2014 42Lines, Inc.
# Original Author: Jim Browne
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime as DT
from lockfile import FileLock, LockFailed, LockTimeout
import logging
import logging.handlers
import __main__ as main
from optparse import OptionParser, make_option
import os
from random import randint
import sys
import time

# Support for RotateFileHandler in multiple processes
from multiprocessinglog import MultiProcessingLog, MultiProcessingLogStream

__version__ = '0.2.1'


class StdErrFilter(logging.Filter):
    ''' Discard all events below a configured level '''

    def __init__(self, level=logging.WARNING, discard_all=False):
        self.level = level
        self.discard_all = discard_all
        super(StdErrFilter, self).__init__()

    def filter(self, record):
        if self.discard_all:
            return False
        else:
            return (record.levelno >= self.level)


class CronScript(object):
    ''' Convenience class for writing cron scripts '''

    def __init__(self, args=None, options=None, usage=None,
                 disable_interspersed_args=False):
        self.lock = None
        self.start_time = None
        self.end_time = None

        if options is None:
            options = []

        if args is None:
            args = sys.argv[1:]

        prog = os.path.basename(main.__file__)
        logfile = os.path.join('/var/log/', "%s.log" % prog)
        lockfile = os.path.join('/var/lock/', "%s.lock" % prog)
        stampfile = os.path.join('/var/tmp/', "%s.success" % prog)
        options.append(make_option("--debug", "-d", action="store_true",
                                   help="Minimum log level of DEBUG"))
        options.append(make_option("--quiet", "-q", action="store_true",
                                   help="Only WARN and above to stdout"))
        options.append(make_option("--nolog", action="store_true",
                                   help="Do not log to LOGFILE"))
        options.append(make_option("--logfile", type="string",
                                   default=logfile,
                                   help="File to log to, default %default"))
        options.append(make_option("--syslog", action="store_true",
                                   help="Log to syslog instead of a file"))
        options.append(make_option("--nolock", action="store_true",
                                   help="Do not use a lockfile"))
        options.append(make_option("--lockfile", type="string",
                                   default=lockfile,
                                   help="Lock file, default %default"))
        options.append(make_option("--nostamp", action="store_true",
                                   help="Do not use a success stamp file"))
        options.append(make_option("--stampfile", type="string",
                                   default=stampfile,
                                   help="Success stamp file, default %default"))
        helpmsg = "Lock timeout in seconds, default %default"
        options.append(make_option("--locktimeout", default=90, type="int",
                                   help=helpmsg))
        helpmsg = "Sleep a random time between 0 and N seconds before starting, default %default"
        options.append(make_option("--splay", default=0, type="int",
                                   help=helpmsg))

        parser = OptionParser(option_list=options, usage=usage)
        if disable_interspersed_args:
            # Stop option parsing at first non-option
            parser.disable_interspersed_args()
        (self.options, self.args) = parser.parse_args(args)

        self.logger = logging.getLogger(main.__name__)

        if self.options.debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # Log to syslog
        if self.options.syslog:
            syslog_formatter = logging.Formatter("%s: %%(levelname)s %%(message)s" % prog)
            handler = logging.handlers.SysLogHandler(
                    address="/dev/log",
                    facility=logging.handlers.SysLogHandler.LOG_LOCAL3
                    )
            handler.setFormatter(syslog_formatter)
            self.logger.addHandler(handler)

        default_formatter = logging.Formatter("%(asctime)s;%(levelname)s;%(message)s",
                                              "%Y-%m-%d-%H:%M:%S")
        if not self.options.nolog:
            # Log to file
            try:
                handler = MultiProcessingLog(
                    "%s" % (self.options.logfile),
                    maxBytes=(50 * 1024 * 1024),
                    backupCount=10)
            except IOError:
                sys.stderr.write("Fatal: Could not open log file: %s\n"
                                 % self.options.logfile)
                sys.exit(1)

            handler.setFormatter(default_formatter)
            self.logger.addHandler(handler)

        # If quiet, only WARNING and above go to STDERR; otherwise all
        # logging goes to stderr
        handler2 = MultiProcessingLogStream(sys.stderr)
        if self.options.quiet:
            err_filter = StdErrFilter()
            handler2.addFilter(err_filter)
        handler2.setFormatter(default_formatter)
        self.logger.addHandler(handler2)

        self.logger.debug(self.options)

    def __enter__(self):
        if self.options.splay > 0:
            splay = randint(0, self.options.splay)
            self.logger.debug('Sleeping for %d seconds (splay=%d)' %
                              (splay, self.options.splay))
            time.sleep(splay)
        self.start_time = DT.datetime.today()
        if not self.options.nolock:
            self.logger.debug('Attempting to acquire lock %s (timeout %s)',
                              self.options.lockfile,
                              self.options.locktimeout)
            self.lock = FileLock(self.options.lockfile)
            try:
                self.lock.acquire(timeout=self.options.locktimeout)
            except LockFailed as e:
                self.logger.error("Lock could not be acquired.")
                self.logger.error(str(e))
                sys.exit(1)
            except LockTimeout as e:
                msg = "Lock could not be acquired. Timeout exceeded."
                self.logger.error(msg)
                sys.exit(1)

    def __exit__(self, etype, value, traceback):
        self.end_time = DT.datetime.today()
        self.logger.debug('Run time: %s', self.end_time - self.start_time)
        if not self.options.nolock:
            self.logger.debug('Attempting to release lock %s',
                              self.options.lockfile)
            self.lock.release()
        if etype is None:
            if not self.options.nostamp:
                open(self.options.stampfile, "w")
