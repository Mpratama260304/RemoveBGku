import json
import logging
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def __init__(self, *args, environment="development", **kwargs):
        super().__init__(*args, **kwargs)
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": self.environment,
        }
        for key in ("request_id", "job_id"):
            if value := getattr(record, key, None):
                data[key] = str(value)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)
