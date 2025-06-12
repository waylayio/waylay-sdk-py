"""Types from the httpx library."""

import ssl
from typing import IO, List, Mapping, Optional, Sequence, Tuple, Union

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
RequestContent = Union[_RequestContent, IO[bytes]]
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
VerifyTypes = Union[ssl.SSLContext, str, bool]

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
