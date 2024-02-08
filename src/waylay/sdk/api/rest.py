"""REST client implementation."""

from io import BufferedReader
from typing import Any, Mapping, Optional, Tuple, Union
from typeguard import check_type
import httpx
import httpx._types as httpx_types

from .api_exceptions import ApiValueError

RESTResponse = httpx.Response
RESTTimeout = Union[
    Optional[float],
    Tuple[Optional[float], Optional[float], Optional[float], Optional[float]],
]


class RESTClient:
    """Base REST client."""

    def __init__(self, *args, **kwargs) -> None:
        """Create an instance."""
        self.client = httpx.AsyncClient(*args, **kwargs)

    async def request(
        self,
        method: str,
        url: httpx._types.URLTypes,
        query: Optional[httpx_types.QueryParamTypes] = None,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[Any] = None,
        files: Optional[httpx_types.RequestFiles] = None,
        _request_timeout: Optional[RESTTimeout] = None
    ) -> RESTResponse:
        """Perform requests.

        :param method: http request method
        :param url: http request url
        :param query: http query parameters
        :param headers: http request headers
        :param body: request json body, for `application/json`
        :param files: request file parameters (`multipart/form-data`)
        :param _request_timeout: timeout setting for this request. If
            one number provided, it will be total request timeout. It
            can also be a pair (tuple) of (connection, read) timeouts.

        """
        method = method.upper()
        headers = headers or {}

        if method not in [
            'GET',
            'HEAD',
            'DELETE',
            'POST',
            'PUT',
            'PATCH',
            'OPTIONS'
        ]:
            raise ApiValueError(
                "Method {0} is not supported.".format(method)
            )

        if files and body:
            raise ApiValueError(
                "The `body` and `files` params are mutually exclusive."
            )

        kwargs: dict[str, Any] = {
            'method': method,
            'url': url,
            'params': query,
            'headers': headers
        }

        if _request_timeout and check_type(_request_timeout, RESTTimeout):
            kwargs['timeout'] = _request_timeout

        # For `POST`, `PUT`, `PATCH`, `OPTIONS`, `DELETE`
        if method in ['POST', 'PUT', 'PATCH', 'OPTIONS', 'DELETE']:
            content_type = headers.get('content-type')
            if files or content_type and content_type == 'multipart/form-data':
                kwargs.update({'files': files})
            elif isinstance(body, (bytes, bytearray, BufferedReader)):
                if isinstance(body, BufferedReader):
                    body = body.read()
                if not headers.get('content-type'):
                    # try:
                    #     import magic
                    #     mime_type = magic.from_buffer(body)
                    # except BaseException:
                    mime_type = 'application/octet-stream'
                    kwargs['headers'].update({'content-type': mime_type})
                    kwargs.update({'content': body})
            elif content_type and content_type != 'application/json':
                kwargs.update({'data': body})
            else:
                kwargs.update({'json': body})

        return await self.client.request(**kwargs)
