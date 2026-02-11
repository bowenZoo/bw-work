"""Structured logging configuration with hourly file rotation."""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path


class HourlyFileHandler(logging.Handler):
    """Log handler that creates one folder per day and one file per hour.

    Directory structure:
        {log_dir}/
            2026-02-10/
                08.log
                09.log
            2026-02-11/
                ...
    """

    def __init__(self, log_dir: str = "logs"):
        super().__init__()
        self.log_dir = Path(log_dir)
        self._current_hour: tuple[str, str] | None = None
        self._stream = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            now = datetime.now()
            hour_key = (now.strftime("%Y-%m-%d"), now.strftime("%H"))
            if hour_key != self._current_hour:
                self._rotate(hour_key)
            if self._stream:
                self._stream.write(self.format(record) + "\n")
                self._stream.flush()
        except Exception:
            self.handleError(record)

    def _rotate(self, hour_key: tuple[str, str]) -> None:
        if self._stream:
            try:
                self._stream.close()
            except Exception:
                pass
        day_dir = self.log_dir / hour_key[0]
        day_dir.mkdir(parents=True, exist_ok=True)
        self._stream = open(day_dir / f"{hour_key[1]}.log", "a", encoding="utf-8")
        self._current_hour = hour_key

    def close(self) -> None:
        if self._stream:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        super().close()


def setup_logging(
    log_dir: str = "logs",
    level: str = "INFO",
) -> None:
    """Configure global logging: console + hourly file handler.

    Args:
        log_dir: Directory for log files.
        level: Log level (DEBUG, INFO, WARNING, ERROR).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (preserves Docker log capture)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # Hourly file handler
    file_handler = HourlyFileHandler(log_dir)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def cleanup_old_logs(
    log_dir: str = "logs",
    keep_days: int = 30,
) -> int:
    """Remove log directories older than keep_days.

    Args:
        log_dir: Directory containing date-named subdirectories.
        keep_days: Number of days to retain.

    Returns:
        Number of directories removed.
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=keep_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    removed = 0

    for entry in sorted(log_path.iterdir()):
        if entry.is_dir() and entry.name < cutoff_str:
            try:
                shutil.rmtree(entry)
                removed += 1
            except Exception:
                pass

    return removed
