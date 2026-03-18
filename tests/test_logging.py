"""
tests/test_logging.py - Tests for MMGI runtime logger.
"""

import sys
import time
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_mmgi_logger  # noqa: E402


def test_mmgi_log_file_created_and_writable():
    logger = get_mmgi_logger()
    logger.info('Logging smoke test message')

    log_file = Path(__file__).parent.parent / 'logs' / 'mmgi.log'
    timeout_at = time.time() + 2.0
    while time.time() < timeout_at and not log_file.exists():
        time.sleep(0.05)

    assert log_file.exists()
