""" Exceptions """

from typing import Any, Optional
from typing_extensions import Self

from httpx import Response as RESTResponse

from waylay.exceptions import RequestError, RestResponseError

class ApiTypeError(RequestError, TypeError):
    def __init__(self, msg, path_to_item=None, valid_classes=None,
                 key_type=None) -> None:
        """ Raises an exception for TypeErrors

        Args:
            msg (str): the exception message

        Keyword Args:
            path_to_item (list): a list of keys an indices to get to the
                                 current_item
                                 None if unset
            valid_classes (tuple): the primitive classes that current item
                                   should be an instance of
                                   None if unset
            key_type (bool): False if our value is a value in a dict
                             True if it is a key in a dict
                             False if our item is an item in a list
                             None if unset
        """
        self.path_to_item = path_to_item
        self.valid_classes = valid_classes
        self.key_type = key_type
        full_msg = msg
        if path_to_item:
            full_msg = "{0} at {1}".format(msg, render_path(path_to_item))
        super(ApiTypeError, self).__init__(full_msg)


class ApiValueError(RequestError, ValueError):
    def __init__(self, msg, path_to_item=None) -> None:
        """
        Args:
            msg (str): the exception message

        Keyword Args:
            path_to_item (list) the path to the exception in the
                received_data dict. None if unset
        """

        self.path_to_item = path_to_item
        full_msg = msg
        if path_to_item:
            full_msg = "{0} at {1}".format(msg, render_path(path_to_item))
        super(ApiValueError, self).__init__(full_msg)


class ApiAttributeError(RequestError, AttributeError):
    def __init__(self, msg, path_to_item=None) -> None:
        """
        Raised when an attribute reference or assignment fails.

        Args:
            msg (str): the exception message

        Keyword Args:
            path_to_item (None/list) the path to the exception in the
                received_data dict
        """
        self.path_to_item = path_to_item
        full_msg = msg
        if path_to_item:
            full_msg = "{0} at {1}".format(msg, render_path(path_to_item))
        super(ApiAttributeError, self).__init__(full_msg)


class ApiKeyError(RequestError, KeyError):
    def __init__(self, msg, path_to_item=None) -> None:
        """
        Args:
            msg (str): the exception message

        Keyword Args:
            path_to_item (None/list) the path to the exception in the
                received_data dict
        """
        self.path_to_item = path_to_item
        full_msg = msg
        if path_to_item:
            full_msg = "{0} at {1}".format(msg, render_path(path_to_item))
        super(ApiKeyError, self).__init__(full_msg)


class ApiError(RestResponseError):

    def __init__(
        self, 
        status: Optional[int] = None, 
        reason: Optional[str] = None, 
        http_resp: Optional[RESTResponse] = None,
        *,
        content: Optional[bytes] = None,
        data: Optional[Any] = None,
    ) -> None:
        self.status_code = status
        self.reason = reason
        self.content = content
        self.data = data
        self.headers = None
        self.url = None
        self.method = None

        if http_resp:
            self.url = http_resp.url
            try: 
                self.method = http_resp.request.method
            except RuntimeError: 
                pass
            if self.status_code is None:
                self.status_code = http_resp.status_code
            if self.reason is None:
                self.reason = http_resp.reason_phrase
            if self.content is None:
                try:
                    self.content = http_resp.content
                except Exception:
                    pass
            self.headers = http_resp.headers

    @classmethod
    def from_response(
        cls, 
        *, 
        http_resp: Optional[RESTResponse] = None, 
        content: Optional[bytes], 
        data: Optional[Any],
    ) -> Self:
        if 400 <= http_resp.status_code <= 499:
            # TODO throw specific errors? e.g. `NotFoundException`, `UnauthorizedException` ...
            raise ApiError(http_resp=http_resp, content=content, data=data)

        if 500 <= http_resp.status_code <= 599:
            raise ApiError(http_resp=http_resp, content=content, data=data)
        raise ApiError(http_resp=http_resp, content=content, data=data)

    def __str__(self):
        """Custom error messages for exception"""

        error_message = "{0}({1})\n"\
                        "Reason: {2}\n".format(self.__class__.__name__, self.status_code, self.reason)
        if self.url and self.method:
            error_message += "{0} {1}\n".format(self.method, self.url)
        
        if self.headers:
            error_message += "HTTP response headers: {0}\n".format(
                self.headers)

        if self.data or self.content:
            error_message += "HTTP response content: {0}\n".format(self.data or str(self.content))

        return error_message + "\n)"


def render_path(path_to_item):
    """Returns a string representation of a path"""
    result = ""
    for pth in path_to_item:
        if isinstance(pth, int):
            result += "[{0}]".format(pth)
        else:
            result += "['{0}']".format(pth)
    return result
