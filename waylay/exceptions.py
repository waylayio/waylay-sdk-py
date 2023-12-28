"""Base exception class hierarchy for errors in the waylay client."""


class WaylayError(Exception):
    """Root class for all exceptions raised by this module."""


class AuthError(WaylayError):
    """Exception class for waylay authentication errors."""


class ConfigError(WaylayError):
    """Exception class for waylay client configuration."""


class RequestError(WaylayError):
    """Exception class for request validation errors within the waylay client.

    Notifies errors in tools and utilities that are not directly related to a REST call.
    """


class RestConnectionError(RequestError):
    """Exception class for request errors that are caused by client connection errors."""


class RestError(WaylayError):
    """Exception class for failures to make a REST call."""


class RestRequestError(RestError):
    """Exception class for failures to prepare a REST call."""


class RestResponseError(RestError):
    """Exception class wrapping the response data of a REST call."""

    def __init__(self, message, response):
        """Wrap a REST response in an error."""
        super().__init__(message)
        self.response = response

    @property
    def message(self):
        """Get the user message for this error."""
        return self.args[0]

    def __str__(self):
        """Render the error to a user-friendly string."""
        try:
            return (
                f"{self.__class__.__name__}({self.response.status_code}: " +
                f"'{self.message}'; {self.response.method} '{self.response.url}')"
            )
        except AttributeError:
            return format(self.response)

    def _get_from_body(self, key, default_value):
        # utility for subclasses in overriding the `message` method
        error_resp_body = self.response.body
        if isinstance(error_resp_body, dict):
            return error_resp_body.get(key, default_value)
        return default_value


class RestResponseParseError(RestResponseError):
    """Exception raised when a successfull http request (200) could not be parsed succesfully."""
