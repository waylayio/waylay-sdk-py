"""Types from the httpx library."""

from typing import IO, List, Mapping, Optional, Sequence, Tuple, Union

from httpx._client import (
    AsyncBaseTransport,
    AuthTypes,
    CertTypes,
    CookieTypes,
    Limits,
    ProxiesTypes,
    ProxyTypes,
    RequestData,
    RequestExtensions,
    RequestFiles,
    TimeoutTypes,
    VerifyTypes,
)
from httpx._client import (
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
    "ProxiesTypes",
    "AsyncBaseTransport",
    "Limits",
    "CertTypes",
    "ProxyTypes",
]
