import json
import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from services.logging_service import (
    JsonFormatter,
    read_recent_logs,
    log_path,
    bind_extra,
    configure_logging,
    monotonic_ms,
)


def test_json_formatter_extra_keys():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="test message", args=(), exc_info=None,
    )
    record._extra = {"user_id": 1}
    record._private = "should_skip"
    result = json.loads(formatter.format(record))
    assert result["user_id"] == 1
    assert "_private" not in result


def test_json_formatter_exception():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="error occurred", args=(), exc_info=None,
    )
    try:
        raise ValueError("test error")
    except ValueError:
        import sys
        record.exc_info = sys.exc_info()
    result = json.loads(formatter.format(record))
    assert "exception" in result
    assert "ValueError" in result["exception"]


def test_read_recent_logs_no_file():
    with patch("services.logging_service.LOG_FILE", Path("/nonexistent/path.log")):
        assert read_recent_logs() == []


def test_read_recent_logs_invalid_json(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("not valid json\n{\"valid\": true}\n")
    with patch("services.logging_service.LOG_FILE", log_file):
        entries = read_recent_logs(limit=10)
        assert len(entries) == 2
        assert entries[0]["level"] == "UNKNOWN"
        assert entries[1]["valid"] is True


def test_log_path():
    path = log_path()
    assert isinstance(path, Path)


def test_bind_extra():
    extra = bind_extra(user_id=1, action="test")
    assert extra == {"_extra": {"user_id": 1, "action": "test"}}


def test_monotonic_ms():
    result = monotonic_ms(0.0)
    assert isinstance(result, int)
    assert result > 0


def test_configure_logging_idempotent():
    import logging
    root = logging.getLogger()
    root._ai_task_manager_logging_configured = False
    tmpdir = tempfile.mkdtemp()
    try:
        log_file = Path(tmpdir) / "test.log"
        with patch("services.logging_service.LOG_DIR", Path(tmpdir)):
            with patch("services.logging_service.LOG_FILE", log_file):
                configure_logging()
                assert root._ai_task_manager_logging_configured is True
                configure_logging()
    finally:
        for h in root.handlers[:]:
            if isinstance(h, logging.FileHandler) and hasattr(h, "baseFilename") and tmpdir in h.baseFilename:
                h.close()
                root.removeHandler(h)
        root._ai_task_manager_logging_configured = False
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
