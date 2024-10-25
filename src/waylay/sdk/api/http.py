"""Aliases for the http client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    Callable,
    TypedDict,
)

import httpx
from typing_extensions import Required  # >=3.11

from . import httpx_types
from .httpx_types import (
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestFiles,
)

AsyncClient = httpx.AsyncClient
Response = httpx.Response
Request = httpx.Request


class HttpRequestArguments(TypedDict, total=False):
    """Call parameters supported in an httpx request."""

    method: Required[str]
    url: Required[httpx_types.URLTypes]
    content: RequestContent
    data: RequestData
    files: RequestFiles
    json: Any
    params: QueryParamTypes
    headers: HeaderTypes
    cookies: httpx_types.CookieTypes
    auth: httpx_types.AuthTypes
    follow_redirects: bool
    timeout: httpx_types.TimeoutTypes
    extensions: httpx_types.RequestExtensions


class HttpClientOptions(TypedDict, total=False):
    """Options passed to the httpx client."""

    auth: httpx_types.AuthTypes | None  # explicit None do disable auth
    params: QueryParamTypes
    headers: HeaderTypes
    cookies: httpx_types.CookieTypes
    verify: httpx_types.VerifyTypes
    cert: httpx_types.CertTypes
    http1: bool
    http2: bool
    proxy: httpx_types.ProxyTypes
    proxies: httpx_types.ProxiesTypes
    mounts: Mapping[str, httpx_types.AsyncBaseTransport | None]
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
