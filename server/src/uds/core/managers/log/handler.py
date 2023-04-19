import logging
import logging.handlers

class UDSLog(logging.handlers.RotatingFileHandler):
    """
    Custom log handler that will log to database before calling to RotatingFileHandler
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Currently, simply call to parent
        msg = self.format(record)  # pylint: disable=unused-variable

        # TODO: Log message on database and continue as a RotatingFileHandler
        return super().emit(record)
