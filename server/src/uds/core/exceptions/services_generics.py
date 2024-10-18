from .common import UDSException


class Error(UDSException):
    """
    Base exception for this module
    """

    pass


class RetryableError(Error):
    """
    Exception that is raised when an error is detected that can be retried
    """

    def __init__(self, message: str):
        super().__init__(message)


class FatalError(Error):
    """
    Exception that is raised when an error is detected that can't be retried
    """

    def __init__(self, message: str):
        super().__init__(message)


class NotFoundError(Error):
    """
    Exception that is raised when an object is not found
    """

    def __init__(self, message: str):
        super().__init__(message)


class AlreadyExistsError(Error):
    """
    Exception that is raised when an object already exists
    """

    def __init__(self, message: str):
        super().__init__(message)
