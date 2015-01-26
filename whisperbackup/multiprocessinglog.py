from logging.handlers import RotatingFileHandler
import multiprocessing, threading, logging, sys, traceback

class MultiProcessingLog(logging.Handler):

    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=0):
        logging.Handler.__init__(self)

        # In case our call to RotatingFileHandler blows up we first set
        # the _handler to None
        self._handler = None
        self._handler = RotatingFileHandler(filename, mode, maxBytes, backupCount,
                                            encoding, delay)
        self.queue = multiprocessing.Queue(-1)

        t = threading.Thread(target=self.receive)
        t.daemon = True
        t.start()

    def setFormatter(self, fmt):
        logging.Handler.setFormatter(self, fmt)
        self._handler.setFormatter(fmt)

    def receive(self):
        while True:
            try:
                record = self.queue.get()
                self._handler.emit(record)
            except (KeyboardInterrupt, SystemExit):
                raise
            except EOFError:
                break
            except:
                traceback.print_exc(file=sys.stderr)

    def send(self, s):
        self.queue.put_nowait(s)

    def _format_record(self, record):
        # ensure that exc_info and args
        # have been stringified.  Removes any chance of
        # unpickleable things inside and possibly reduces
        # message size sent over the pipe
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        if record.exc_info:
            dummy = self.format(record)
            record.exc_info = None

        return record

    def emit(self, record):
        try:
            s = self._format_record(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        if self._handler is not None:
            self._handler.close()
        logging.Handler.close(self)


class MultiProcessingLogStream(MultiProcessingLog):

    def __init__(self, stream=None):
        logging.Handler.__init__(self)

        # In case our call to StreamHandler blows up we first set
        # the _handler to None
        self._handler = None
        self._handler = logging.StreamHandler(stream)
        self.queue = multiprocessing.Queue(-1)

        t = threading.Thread(target=self.receive)
        t.daemon = True
        t.start()
