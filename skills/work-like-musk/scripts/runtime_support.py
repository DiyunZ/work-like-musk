"""Operating-system locks shared by the reporter, installer, and portable HUD."""
from contextlib import contextmanager
import errno
import os
import time


@contextmanager
def file_lock(stream, blocking=True):
    """Exclusively lock an open file; release only a successfully acquired lock."""
    if os.name == 'nt':
        import msvcrt
        # Windows byte-range locks can extend past EOF; no sentinel write is needed.
        while True:
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if not blocking:
                    raise BlockingIOError(error.errno, 'File lock is held by another process') from error
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        fcntl.flock(stream.fileno(), flags)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
