"""REST client implementation."""

from io import BufferedReader
from typing import Any, Optional
import httpx
from waylay.api.api_config import ApiConfig

from waylay.api.api_exceptions import ApiValueError

RESTResponse = httpx.Response


class RESTClient:
    """Base REST client."""

    def __init__(self, configuration: ApiConfig) -> None:
        """Create an instance."""
        additional_httpx_kwargs = {
            "verify": configuration.ssl_ca_cert,
        }

        self.client = httpx.AsyncClient(
            auth=configuration.waylay_config.auth,
            **additional_httpx_kwargs
        )

    async def request(
        self,
        method,
        url,
        query=None,
        headers=None,
        body=None,
        files=None,
        _request_timeout=None
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

        assert method in [
            'GET',
            'HEAD',
            'DELETE',
            'POST',
            'PUT',
            'PATCH',
            'OPTIONS'
        ]

        if files and body:
            raise ApiValueError(
                "body parameter cannot be used with files parameter."
            )

        timeout: Optional[Any] = None
        if _request_timeout:
            if isinstance(_request_timeout, (int, float)):
                timeout = _request_timeout
            elif (
                isinstance(_request_timeout, tuple)
                and len(_request_timeout) == 2
            ):
                timeout = _request_timeout

        kwargs = {
            'method': method,
            'url': url,
            'params': query,
            'timeout': timeout,
            'headers': headers
        }

        # For `POST`, `PUT`, `PATCH`, `OPTIONS`, `DELETE`
        if method in ['POST', 'PUT', 'PATCH', 'OPTIONS', 'DELETE']:
            content_type = headers.get('Content-Type')
            if files or content_type and content_type == 'multipart/form-data':
                kwargs.update({'files': files})
            elif isinstance(body, (bytes, bytearray, BufferedReader)):
                if isinstance(body, BufferedReader):
                    body = body.read()
                if not headers.get('content-type'):
                    try:
                        import magic
                        mime_type = magic.from_buffer(body)
                    except BaseException:
                        mime_type = 'application/octet-stream'
                    kwargs['headers'].update({'content-type': mime_type})
                    kwargs.update({'content': body})
            elif content_type and content_type != 'application/json':
                kwargs.update({'data': body})
            else:
                kwargs.update({'json': body})

        return await self.client.request(**kwargs)
