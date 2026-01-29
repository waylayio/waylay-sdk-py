"""Types from the httpx library."""

import ssl
from collections.abc import Mapping, Sequence
from typing import IO

from httpx._client import (
    AsyncBaseTransport,
    Limits,
)
from httpx._types import (
    AuthTypes,
    CertTypes,
    CookieTypes,
    ProxyTypes,
    RequestData,
    RequestExtensions,
    RequestFiles,
    TimeoutTypes,
)
from httpx._types import (
    RequestContent as _RequestContent,
)

URLTypes = str
# allow any IO as request content, converted to an AsyncIterable at
#  waylay.sdk.api.serialization._convert_content
RequestContent = _RequestContent | IO[bytes]
HeaderTypes = (
    Mapping[str, str]
    | Mapping[bytes, bytes]
    | Sequence[tuple[str, str]]
    | Sequence[tuple[bytes, bytes]]
)

PrimitiveData = str | int | float | bool | None
QueryParamTypes = (
    Mapping[str, PrimitiveData | Sequence[PrimitiveData]]
    | list[tuple[str, PrimitiveData]]
    | tuple[tuple[str, PrimitiveData], ...]
    | str
    | bytes
)
VerifyTypes = ssl.SSLContext | str | bool

__all__ = [
    "RequestFiles",
    "RequestData",
    "URLTypes",
    "RequestContent",
    "AuthTypes",
    "TimeoutTypes",
    "CookieTypes",
    "QueryParamTypes",
    "RequestExtensions",
    "VerifyTypes",
    "ProxyTypes",
    "AsyncBaseTransport",
    "Limits",
    "CertTypes",
    "ProxyTypes",
]
