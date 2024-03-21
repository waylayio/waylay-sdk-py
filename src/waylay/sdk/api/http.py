"""Aliases for the http client."""

from __future__ import annotations
from typing import (
    TypedDict,
    Mapping,
    Optional,
    Callable,
    Any,
    Union,
    Sequence,
    Tuple,
    List,
    IO,
)
from typing_extensions import Required  # >=3.11

import httpx._client as httpx_types
import httpx

AsyncClient = httpx.AsyncClient
Response = httpx.Response
Request = httpx.Request

HeaderTypes = Union[
    Mapping[str, str],
    Mapping[bytes, bytes],
    Sequence[Tuple[str, str]],
    Sequence[Tuple[bytes, bytes]],
]

PrimitiveData = Optional[Union[str, int, float, bool]]
QueryParamTypes = Union[
    Mapping[str, Union[PrimitiveData, Sequence[PrimitiveData]]],
    List[Tuple[str, PrimitiveData]],
    Tuple[Tuple[str, PrimitiveData], ...],
    str,
    bytes,
]

RequestFiles = httpx_types.RequestFiles
RequestContent = Union[httpx_types.RequestContent, IO[bytes]]
RequestData = httpx_types.RequestData


class HttpRequestArguments(TypedDict, total=False):
    """Call parameters supported in an httpx request."""

    method: Required[str]
    url: Required[httpx_types.URLTypes]
    content: httpx_types.RequestContent
    data: httpx_types.RequestData
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

    auth: Optional[httpx_types.AuthTypes]  # explicit None do disable auth
    params: httpx_types.QueryParamTypes
    headers: HeaderTypes
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
