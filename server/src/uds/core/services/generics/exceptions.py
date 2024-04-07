from uds.core import exceptions as core_exceptions


class RetryableError(core_exceptions.UDSException):
    """
    Exception that is raised when an error is detected that can be retried
    """

    def __init__(self, message: str):
        super().__init__(message)


class FatalError(core_exceptions.UDSException):
    """
    Exception that is raised when an error is detected that can't be retried
    """

    def __init__(self, message: str):
        super().__init__(message)


class NotFoundError(core_exceptions.UDSException):
    """
    Exception that is raised when an object is not found
    """

    def __init__(self, message: str):
        super().__init__(message)
