"""Aliases for the http client."""
from typing import TypedDict, Mapping, Optional, Callable, Any

import httpx._client as httpx_types
import httpx

AsyncClient = httpx.AsyncClient
Response = httpx.Response


class HttpClientOptions(TypedDict, total=False):
    """Options passed to the httpx client."""

    auth: Optional[httpx_types.AuthTypes]  # explicit None do disable auth
    params: httpx_types.QueryParamTypes
    headers: httpx_types.HeaderTypes
    cookies: httpx_types.CookieTypes
    verify: httpx_types.VerifyTypes
    cert: httpx_types.CertTypes
    http1: bool
    http2: bool
    proxy: httpx_types.ProxyTypes
    proxies: httpx_types.ProxiesTypes
    mounts: Mapping[str, Optional[httpx_types.AsyncBaseTransport]]
    timeout: httpx_types.TimeoutTypes
    follow_redirects: bool
    limits: httpx_types.Limits
    max_redirects: int
    event_hooks: Mapping[str, list[Callable[..., Any]]]
    base_url: str
    transport: httpx_types.AsyncBaseTransport
    app: Callable[..., Any]
    trust_env: bool
    default_encoding: str | Callable[[bytes], str]
