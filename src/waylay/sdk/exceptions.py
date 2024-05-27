"""Base exception class hierarchy for errors in the waylay client."""

from __future__ import annotations

from .api.http import Request, Response


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
    """Exception class for request errors caused by client connection errors."""


class RestError(WaylayError):
    """Exception class for failures to make a REST call."""


class RestRequestError(RestError):
    """Exception class for failures to prepare a REST call."""

    request: Request | None

    def __init__(
        self,
        *args,
        request: Request | None = None,
    ):
        """Create an instance."""
        super().__init__(*args)
        self.request = request

    def __str__(self):
        """Get the string representation of the exception."""
        error_message = super().__str__()
        if self.request is None:
            return error_message
        req = self.request
        error_message += f"\nRequest: {req.method} {req.url}"
        if req.headers:
            error_message += f"\nRequest headers: {req.headers}"
        if hasattr(req, "_content"):
            error_message += f"\nRequest content: <bytes: len={len(req._content)}>"
        else:
            error_message += f"\nRequest content: <streaming: {req.stream}>"
        return error_message


class RestResponseError(RestRequestError):
    """Exception class wrapping the response data of a REST call."""

    response: Response

    def __init__(
        self,
        *args,
        response: Response,
    ) -> None:
        """Create an instance."""
        super().__init__(*args, request=response._request)
        self.response = response

    def __str__(self):
        """Get the string representation of the exception."""
        error_message = super().__repr__()
        resp = self.response
        error_message += f"\nStatus: {resp.status_code}"
        error_message += f"\nReason: {resp.reason_phrase}"
        if resp.headers:
            error_message += f"\nResponse headers: {resp.headers}"
        if hasattr(self.response, "_content"):
            error_message += f"\nResponse content: <bytes: len={len(resp._content)}>"
        else:
            error_message += (
                f"\nResponse content: <streaming: len={resp.num_bytes_downloaded}>"
            )
        return error_message


class RestResponseParseError(RestResponseError):
    """Exception raised when a successfull http request (2XX) could not be parsed."""
