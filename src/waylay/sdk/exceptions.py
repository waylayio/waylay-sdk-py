"""Base exception class hierarchy for errors in the waylay client."""


class WaylayError(Exception):
    """Root class for all exceptions raised by this module."""


class ConfigError(WaylayError):
    """Exception class for waylay client configuration."""


class RequestError(WaylayError):
    """Exception class for request validation errors within the waylay client.

    Notifies errors in tools and utilities that are not directly related
    to a REST call.
    """


class RestConnectionError(RequestError):
    """Exception class for request errors that are caused by client connection errors."""


class RestError(WaylayError):
    """Exception class for failures to make a REST call."""


class RestRequestError(RestError):
    """Exception class for failures to prepare a REST call."""


class RestResponseError(RestError):
    """Exception class wrapping the response data of a REST call."""


class RestResponseParseError(RestResponseError):
    """Exception raised when a successfull http request (200) could not be parsed succesfully."""
