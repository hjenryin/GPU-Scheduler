
class SchedulerException(Exception):
    """Base exception for scheduler errors"""
    pass


class NodeNotFoundException(SchedulerException):
    """Raised when node is not found"""
    pass


class JobNotFoundException(SchedulerException):
    """Raised when job is not found"""
    pass


class InvalidRequirementException(SchedulerException):
    """Raised when job requirement is invalid"""
    pass


class ConnectionException(SchedulerException):
    """Raised when connection to head node fails"""
    pass


class ValidationException(SchedulerException):
    """Raised when validation fails"""
    pass


class TimeoutException(SchedulerException):
    """Raised when operation times out"""
    pass


class PermissionDeniedException(SchedulerException):
    """Raised when permission is denied"""
    pass
