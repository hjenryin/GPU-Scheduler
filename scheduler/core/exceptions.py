
class SchedulerException(Exception):
    """Base exception for scheduler errors.
    
    All scheduler-specific exceptions inherit from this class.
    """
    pass


class NodeNotFoundException(SchedulerException):
    """Raised when a requested node is not found.
    
    This exception is raised when trying to access a node that doesn't exist
    in the cluster registry.
    """
    pass


class JobNotFoundException(SchedulerException):
    """Raised when a requested job is not found.
    
    This exception is raised when trying to access a job that doesn't exist
    in the job queue or has been removed.
    """
    pass


class InvalidRequirementException(SchedulerException):
    """Raised when job requirement specification is invalid.
    
    This exception is raised when the resource requirement string cannot be
    parsed or contains invalid values (e.g., negative GPU counts, invalid node names).
    """
    pass


class ConnectionException(SchedulerException):
    """Raised when connection to head node fails.
    
    This exception is raised when the client cannot establish a connection
    to the head node, either due to network issues or the head node being down.
    """
    pass


class ValidationException(SchedulerException):
    """Raised when input validation fails.
    
    This exception is raised when provided parameters fail validation checks,
    such as invalid configuration values or malformed requests.
    """
    pass


class TimeoutException(SchedulerException):
    """Raised when an operation times out.
    
    This exception is raised when an operation takes longer than the expected
    timeout period, such as waiting for a job to complete or connecting to a node.
    """
    pass


class PermissionDeniedException(SchedulerException):
    """Raised when permission is denied.
    
    This exception is raised when the operation cannot be performed due to
    insufficient permissions, such as trying to bind to a privileged port.
    """
    pass
