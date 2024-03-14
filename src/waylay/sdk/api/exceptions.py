"""Exceptions."""

from typing import Any, Optional

from .http import Response

from ..exceptions import WaylayError, RequestError, RestResponseError


class ApiValueError(RequestError, ValueError):
    """Inappropriate argument value (of correct type) in a Waylay API request."""

    def __init__(self, msg, path_to_item=None) -> None:
        """Raise a value error.

        Args:
            msg (str): the exception message

        Keyword Args:
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

    data: Optional[Any]

    def __init__(
        self,
        response: Response,
        data: Optional[Any],
    ) -> None:
        """Create an instance."""
        super().__init__(response)
        self.data = data

    @classmethod
    def from_response(
        cls,
        response: Response,
        data: Optional[Any],
    ):
        """Create an instance from a REST exception response."""
        return cls(response, data)

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
