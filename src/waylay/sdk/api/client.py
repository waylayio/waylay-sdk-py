"""API client."""
from typing import Any, Mapping, Optional, Tuple, Union, AsyncIterable
from io import BufferedReader

from ..__version__ import __version__
from ..config import WaylayConfig

from .exceptions import SyncCtxMgtNotSupportedError
from .serialization import WithSerializationSupport
from .exceptions import ApiValueError
from .http import AsyncClient, Response, HttpClientOptions

RESTTimeout = Union[
    Optional[float],
    Tuple[Optional[float], Optional[float], Optional[float], Optional[float]],
]
_CHUNK_SIZE = 65_536
_ALLOWED_METHODS = ["GET", "HEAD", "DELETE", "POST", "PUT", "PATCH", "OPTIONS"]


class ApiClient(WithSerializationSupport):
    """Generic API client for OpenAPI client library builds.

    OpenAPI generic API client. This client handles the client-server
    communication, and is invariant across implementations. Specifics of
    the methods and models for each application are generated from the
    OpenAPI templates.

    :param configuration: configuration object for this client

    """

    config: WaylayConfig
    http_options: HttpClientOptions
    base_url: str
    _http_client: Optional[AsyncClient]

    def __init__(
        self,
        config: WaylayConfig,
        http_options: Optional[HttpClientOptions | AsyncClient] = None,
    ) -> None:
        """Create an instance."""
        self.config = config
        self.http_options = {}
        self._http_client = None
        self.base_url = self.config.gateway_url
        if http_options:
            self.set_options(http_options)

    def set_options(self, http_options: HttpClientOptions | AsyncClient):
        """Update http options on not open client."""
        if not self.is_closed:
            raise AttributeError("Cannot set options on open client.")
        if isinstance(http_options, AsyncClient):
            self._http_client = http_options
        elif isinstance(http_options, Mapping):
            self.http_options = http_options

    def clone(self, http_options: Optional[HttpClientOptions] = None):
        """Clone api client without http client."""
        http_options = (
            self.http_options
            if http_options is None
            else {**self.http_options, **http_options}
        )
        return self.__class__(self.config, http_options)

    @property
    def http_client(self) -> AsyncClient:
        """Get (or open) a http client."""
        if self._http_client is None or self.is_closed:
            self._http_client = self._init_http_client()
            return self._http_client
        return self._http_client

    @property
    def is_closed(self) -> bool:
        """Check that there is no active http client."""
        if not self._http_client:
            return True
        if self._http_client.is_closed:
            # someone else closed this http client, remove it.
            self._http_client = None
            return True
        return False

    async def __aenter__(self):
        """Initialize the http client."""
        if not self.is_closed:
            raise ValueError("Http client already in use.")
        self._http_client = self._init_http_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the http client."""
        await self.aclose()

    def __enter__(self):
        """Dissallow sync context management for now."""
        raise SyncCtxMgtNotSupportedError(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Disallow sync context management."""
        raise SyncCtxMgtNotSupportedError(self)

    def _init_http_client(self) -> AsyncClient:
        opts = self.http_options
        client = AsyncClient(**opts)
        base_url = opts.get("base_url", self.config.gateway_url)
        client.base_url = base_url  # type: ignore
        auth = opts.get("auth", self.config.auth)
        client.auth = auth  # type: ignore
        client.headers.update({"User-Agent": f"waylay-sdk/python/{__version__}"})
        return client

    async def aclose(self):
        """Close the client."""
        if not self.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def call_api(
        self,
        method: str,
        url: str,
        # v DEPRECATED PARAMETERS: prefer native httpx parameters
        body: Optional[Any] = None,
        query_params: Optional[Mapping[str, Any]] = None,
        header_params: Optional[Mapping[str, str]] = None,
        _request_timeout: Optional[RESTTimeout] = None,
        # ^ DEPRECATED PARAMETERS
        **kwargs,
    ) -> Response:
        """Make a HTTP request."""
        method = _validate_method(method)
        # v DEPRECATED PARAMETERS: prefer native httpx parameters
        timeout = kwargs.pop("timeout", _request_timeout)
        if timeout is not None:
            kwargs["timeout"] = timeout
        params = kwargs.pop("params", query_params)
        if params:
            kwargs["params"] = params
        headers = kwargs.pop("headers", header_params)
        if headers:
            kwargs["headers"] = headers
        if body:
            kwargs.update(self.convert_body(body, kwargs))
        # ^ DEPRECATED PARAMETERS
        # perform request and return response
        return await self.http_client.request(
            method,
            url,
            **kwargs,
        )

    def convert_body(
        self,
        body: Any,
        kwargs,
    ) -> Mapping[str, Any]:
        """SDK invocation request with untyped body."""
        headers = kwargs.pop("headers", None) or {}
        content_type = headers.get("content-type", "")
        if isinstance(body, BufferedReader):

            async def read_buffer():
                while chunk := body.read(_CHUNK_SIZE):
                    yield chunk

            kwargs["content"] = read_buffer()
        elif isinstance(body, (bytes, AsyncIterable)):
            kwargs["content"] = body
        elif content_type.startswith("application/x-www-form-urlencoded"):
            kwargs["data"] = body
        elif not content_type:
            # TBD: check string case
            # body='"abc"', content-type:'application/json' => content='"abc"'
            # body='abc' => json='abc' (encoded '"abc"')
            # body='abc', content-type:'application/json' => content='abc' (invalid)
            kwargs["json"] = body
        else:
            kwargs["content"] = body
        if "content" in kwargs and not content_type:
            headers["content-type"] = "application/octet-stream"
        kwargs["headers"] = headers
        return kwargs


def _validate_method(method: str):
    method = method.upper()
    if method not in _ALLOWED_METHODS:
        raise ApiValueError(f"Method {method} is not supported.")
    return method
