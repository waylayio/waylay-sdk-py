"""API client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional, Tuple, Union

from .._version import __version__
from ..config import WaylayConfig
from .exceptions import SyncCtxMgtNotSupportedError
from .http import AsyncClient, HttpClientOptions, Request, Response
from .serialization import WithSerializationSupport

RESTTimeout = Union[
    Optional[float],
    Tuple[Optional[float], Optional[float], Optional[float], Optional[float]],
]


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
    _http_client: AsyncClient | None

    def __init__(
        self,
        config: WaylayConfig,
        http_options: HttpClientOptions | AsyncClient | None = None,
    ) -> None:
        """Create an instance."""
        self.config = config
        self.http_options = {}
        self._http_client = None
        self.base_url = self.config.gateway_url
        if http_options:
            self.set_options(http_options)

    def set_options(self, http_options: HttpClientOptions | AsyncClient | None):
        """Update http options on not open client."""
        if not self.is_closed:
            raise AttributeError("Cannot set options on open client.")
        if isinstance(http_options, AsyncClient):
            self._http_client = http_options
        elif isinstance(http_options, Mapping):
            self.http_options = http_options

    def clone(self, http_options: HttpClientOptions | None = None):
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
        if self._http_client and not self.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _request(self, *args, **kwargs) -> Response:
        """Invoke a http request."""
        return await self.http_client.request(*args, **kwargs)

    async def send(
        self, request: Request, *, stream: bool = False, **kwargs
    ) -> Response:
        """Send an http request."""
        return await self.http_client.send(request, stream=stream, **kwargs)
