"""Exercise the real Linux serial reader with a pseudo-terminal, not hardware."""
import json
import os
from pathlib import Path
import pty
import signal
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import serial_stream


class SerialReaderTest(unittest.TestCase):
    def test_invalid_and_oversized_lines_are_skipped_before_valid_json(self):
        master, slave = pty.openpty()
        path = os.ttyname(slave)
        expected = {"temperature": 22.5, "humidity": 45, "pressure": 1010}

        def write():
            time.sleep(0.1)  # Allow termios setup/flush before transmitting.
            for data in (b"Arduino boot message\n", b"x" * 4100 + b"\n", json.dumps(expected).encode() + b"\n"):
                os.write(master, data)

        stream = serial_stream(path)
        thread = threading.Thread(target=write, daemon=True)
        thread.start()
        def timeout(*_):
            raise TimeoutError("Serial reader did not return a valid record")
        original = signal.signal(signal.SIGALRM, timeout)
        signal.alarm(5)
        try:
            self.assertEqual(next(stream), expected)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original)
            stream.close()
            thread.join(timeout=1)
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()
