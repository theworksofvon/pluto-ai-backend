import logging
import sys
import os
import json
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path


class PlutoLogger:
    """
    A flexible logger for the Pluto AI project.

    Features:
    - Console and file logging
    - Log rotation
    - JSON output option for structured logging
    - Customizable log levels for different outputs
    - Context tracking (request_id, user_id, etc.)
    """

    def __init__(
        self,
        name: str = "pluto-ai",
        log_level: int = logging.INFO,
        console_logging: bool = True,
        file_logging: bool = True,
        json_logging: bool = False,
        log_dir: str = "logs",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        log_rotation: str = "size",  # "size" or "time"
    ):
        """
        Initialize the logger.

        Args:
            name: Logger name
            log_level: Default logging level
            console_logging: Enable console logging
            file_logging: Enable file logging
            json_logging: Output logs as JSON
            log_dir: Directory for log files
            max_bytes: Max size for log files before rotation
            backup_count: Number of backup files to keep
            log_rotation: Rotation strategy ("size" or "time")
        """
        self.name = name
        self.log_level = log_level
        self.console_logging = console_logging
        self.file_logging = file_logging
        self.json_logging = json_logging
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.log_rotation = log_rotation
        self.context = {}

        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)
        self.logger.propagate = False

        if self.logger.handlers:
            self.logger.handlers.clear()

        if console_logging:
            self._setup_console_handler()

        if file_logging:
            self._setup_file_handler()

    def _setup_console_handler(self):
        """Setup console logging handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)

        if self.json_logging:
            formatter = self._get_json_formatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s - %(pathname)s:%(lineno)d"
            )

        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _setup_file_handler(self):
        """Setup file logging handler"""
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)

        log_file = os.path.join(self.log_dir, f"{self.name}.log")

        if self.log_rotation == "size":
            file_handler = RotatingFileHandler(
                log_file, maxBytes=self.max_bytes, backupCount=self.backup_count
            )
        else:  # time based rotation
            file_handler = TimedRotatingFileHandler(
                log_file, when="midnight", interval=1, backupCount=self.backup_count
            )

        file_handler.setLevel(self.log_level)

        if self.json_logging:
            formatter = self._get_json_formatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s - %(pathname)s:%(lineno)d"
            )

        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _get_json_formatter(self):
        """Returns a JSON formatter for structured logging"""

        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "line": record.lineno,
                    "path": record.pathname,
                }

                # Add exception info if available
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)

                # Add any context variables
                if hasattr(record, "context") and record.context:
                    log_data.update(record.context)

                return json.dumps(log_data)

        return JsonFormatter()

    def set_context(self, **kwargs):
        """
        Set contextual variables to be included in all subsequent log entries.

        Example:
            logger.set_context(request_id='abc123', user_id='user456')
        """
        self.context.update(kwargs)

        # Create a filter to add context to log records
        class ContextFilter(logging.Filter):
            def __init__(self, context_dict):
                super().__init__()
                self.context = context_dict

            def filter(self, record):
                record.context = self.context
                return True

        # Remove previous filters and add the new one
        for handler in self.logger.handlers:
            for f in handler.filters:
                if isinstance(f, ContextFilter):
                    handler.removeFilter(f)
            handler.addFilter(ContextFilter(self.context))

    def clear_context(self):
        """Clear all contextual variables"""
        self.context = {}

        # Remove context filters
        for handler in self.logger.handlers:
            for f in handler.filters:
                if hasattr(f, "context"):
                    handler.removeFilter(f)

    def debug(self, msg, *args, **kwargs):
        """Log a debug message"""
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """Log an info message"""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """Log a warning message"""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """Log an error message"""
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        """Log a critical message"""
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        """Log an exception message"""
        self.logger.exception(msg, *args, **kwargs)


logger = PlutoLogger()
