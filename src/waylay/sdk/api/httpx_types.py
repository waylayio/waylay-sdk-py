"""Types from the httpx library."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx._client import (
        AsyncBaseTransport,
        AuthTypes,
        CertTypes,
        CookieTypes,
        Limits,
        ProxiesTypes,
        ProxyTypes,
        QueryParamTypes,
        RequestContent,
        RequestData,
        RequestExtensions,
        RequestFiles,
        TimeoutTypes,
        URLTypes,
        VerifyTypes,
    )
else:
    AuthTypes = Any
    RequestContent = Any
    RequestData = Any
    RequestFiles = Any
    TimeoutTypes = Any
    URLTypes = Any
    CookieTypes = Any
    QueryParamType = Any
    AsyncBaseTransport = Any
    ProxiesTypes = Any
    Limits = Any
    RequestExtensions = Any
    VerifyTypes = Any
    CertTypes = Any
    ProxyTypes = Any

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
