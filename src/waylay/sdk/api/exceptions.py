"""Exceptions."""

from __future__ import annotations

from typing import Any

from ..exceptions import RequestError, RestResponseError, WaylayError
from .http import Response


class ApiValueError(RequestError, ValueError):
    """Inappropriate argument value (of correct type) in a Waylay API request."""

    def __init__(self, msg: str, path_to_item=None) -> None:
        """Raise a value error.

        Args:
        ----
            msg (str): the exception message
            path_to_item (str): path into the request object

        Keyword Args:
        ------------
            path_to_item (list) the path to the exception in the
                received_data dict. None if unset

        """
        self.path_to_item = path_to_item
        full_msg = msg
        if path_to_item:
            full_msg = f"{msg} at {render_path(path_to_item)}"
        super(ApiValueError, self).__init__(full_msg)


class ApiError(RestResponseError):
    """Exception class wrapping the response data of a REST call."""

    data: Any | None

    def __init__(
        self,
        *args,
        response: Response,
        data: Any | None,
    ) -> None:
        """Create an instance."""
        super().__init__(*args, response=response)
        self.data = data

    @classmethod
    def from_response(
        cls,
        message: str,
        response: Response,
        data: Any | None,
    ):
        """Create an instance from a REST exception response."""
        return cls(message, response=response, data=data)

    def __str__(self):
        """Get the string representation of the exception."""
        error_message = super().__str__()
        if self.data and self.data != self.response.content:
            error_message += f"\nResponse data: {self.data}"
        return error_message


class SyncCtxMgtNotSupportedError(WaylayError, TypeError):
    """Warn the user to use async context management."""

    def __init__(self, target):
        """Create the exception."""
        super().__init__(
            f"{target.__class__.__name__} object "
            "does not support the sync context management protocol.\n"
            'Use async context management instead: "await with ...:"'
        )


def render_path(path_to_item):
    """Return a string representation of a path."""
    result = ""
    for path in path_to_item:
        if isinstance(path, int):
            result += f"[{path}]"
        else:
            result += f"['{path}']"
    return result
