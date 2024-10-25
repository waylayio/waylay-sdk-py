"""API client."""

from __future__ import annotations

import contextlib
import datetime
import json as json_lib
import logging
import re
from abc import abstractmethod
from collections.abc import (
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Iterable,
    Mapping,
)
from inspect import isclass
from typing import (
    Any,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)
from urllib.parse import quote

import httpx._client as httpxc
from httpx import USE_CLIENT_DEFAULT, ResponseNotRead
from jsonpath_ng import parse as jsonpath_parse  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from pydantic_core import to_jsonable_python
from typing_extensions import (
    TypeAlias,  # >=3.9
)

from ._models import Model
from .exceptions import ApiError, ApiValueError, RestResponseError
from .http import (
    AsyncClient,
    HeaderTypes,
    QueryParamTypes,
    Request,
    RequestContent,
    RequestData,
    RequestFiles,
    Response,
)

_DEFAULT_RESPONSE_TYPE = Model
_PRIMITIVE_BYTE_TYPES = (bytes, bytearray)
_CLASS_MAPPING = {
    "date": datetime.date,
    "datetime": datetime.datetime,
    "Any": Any,
}
_ALLOWED_METHODS = ["GET", "HEAD", "DELETE", "POST", "PUT", "PATCH", "OPTIONS"]

_MODEL_TYPE_ADAPTER: Any = TypeAdapter(Model)

log = logging.getLogger(__name__)

TEXT_EVENT_STREAM_CONTENT_TYPE = "text/event-stream"
NDJSON_EVENT_STREAM_CONTENT_TYPE = "application/x-ndjson"
EVENT_STREAM_CONTENT_TYPES = [
    TEXT_EVENT_STREAM_CONTENT_TYPE,
    NDJSON_EVENT_STREAM_CONTENT_TYPE,
]
TypeMapping: TypeAlias = Union[Mapping[str, Optional[Type[Any]]], Type[Any], None]


class WithSerializationSupport:
    """Serialization support for the SDK client."""

    base_url: str

    @property
    @abstractmethod
    def http_client(self) -> AsyncClient:
        """Get (or open) a http client."""

    async def request(
        self,
        method: str,
        resource_path: str,
        path_params: Mapping[str, str] | None = None,
        *,
        params: QueryParamTypes | Mapping | BaseModel | None = None,
        json: Any | None = None,
        content: RequestContent | None = None,
        files: RequestFiles | None = None,
        data: RequestData | None = None,
        headers: HeaderTypes | None = None,
        cookies: httpxc.CookieTypes | None = None,
        timeout: httpxc.TimeoutTypes | None = None,
        extensions: httpxc.RequestExtensions | None = None,
        # Deserialization arguments
        response_type: Mapping[str, Type | None] | Type | None = None,
        select_path: str = "",
        raw_response: bool = False,
        # Additional parameters passed on to the http client
        **kwargs,
    ) -> Response | Any:
        """Perform a request with serialization and deserialization support."""
        # set aside send args
        send_args = {}
        for key in ["stream", "follow_redirects", "auth"]:
            if key in kwargs:
                send_args[key] = kwargs.pop(key)

        api_request = self.build_request(
            method,
            resource_path,
            path_params,
            params=params,
            json=json,
            content=content,
            files=files,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            extensions=extensions,
            **kwargs,
        )
        response = await self.http_client.send(api_request, **send_args)
        if raw_response:
            return response
        return self.deserialize(
            response,
            response_type=response_type,
            select_path=select_path,
            stream=send_args.get("stream", False),
        )

    def build_request(
        self,
        method: str,
        resource_path: str,
        path_params: Mapping[str, str] | None = None,
        *,
        params: QueryParamTypes | Mapping | BaseModel | None = None,
        json: Any | None = None,
        content: RequestContent | None = None,
        files: RequestFiles | None = None,
        data: RequestData | None = None,
        headers: HeaderTypes | None = None,
        cookies: httpxc.CookieTypes | None = None,
        timeout: httpxc.TimeoutTypes | None = None,
        extensions: httpxc.RequestExtensions | None = None,
    ) -> Request:
        """Build the HTTP request params needed by the request."""
        method = _validate_method(method)
        url = _interpolate_resource_path(resource_path, path_params)
        return self.http_client.build_request(
            method,
            url,
            content=_convert_content(content),
            data=self.serialize(data),
            files=files,
            json=self.serialize(json),
            params=self.serialize(params),
            headers=headers,
            cookies=cookies,
            timeout=USE_CLIENT_DEFAULT if timeout is None else timeout,
            extensions=extensions,
        )

    def serialize(self, data):
        """Serialize to a jsonable python data structure."""
        return to_jsonable_python(data, by_alias=True, exclude_none=True)

    def deserialize(
        self,
        response: Response,
        *,
        response_type: TypeMapping = None,
        select_path: str = "",
        stream: bool = False,
    ) -> Any:
        """Deserialize a http response into a python object.

        :param response_data: Response object to be deserialized.
        :param response_type: Response type to use for 2XX status codes,
            or a mapping per status code, including '2XX', '3XX', .. and
            '*' or 'default' wildcard keys.
        :param select_path: json path to be extracted from the json payload.
        :param stream: Whether the response should be in streaming mode.
            If the response is an event stream, this function
            will return an async iterator.
        :return: An instance of the type specified in the mapping, or an async iterator
            for event stream responses when stream is True.
        """
        status_code = response.status_code
        _response_type = _response_type_for_status_code(status_code, response_type)

        if not 200 <= response.status_code <= 299:
            raise ApiError.from_response(
                "Error response.",
                response,
                _deserialize_response(
                    response, response_type=_response_type, select_path=select_path
                ),
            )
        content_type = response.headers.get("content-type", "")
        is_event_stream = any(
            [content_type.startswith(ect) for ect in EVENT_STREAM_CONTENT_TYPES]
        )
        if stream and is_event_stream:
            return _iter_event_stream(
                response, response_type=_response_type, select_path=select_path
            )
        else:
            return _deserialize_response(
                response, response_type=_response_type, select_path=select_path
            )


_CHUNK_SIZE = 65_536


@runtime_checkable
class Readable(Protocol):
    """Anything with a binary read method."""

    def read(self, n: int = -1) -> bytes:
        """Read a binary chunk."""


def _convert_content(content: Any):
    """Convert Iterable and Readable to AsyncIterable."""
    # do not handle cases httpx handles
    if isinstance(content, (bytes, str, AsyncIterable)):
        return content
    # non-dict Iterables fail when using async client, convert to async iterable.
    if isinstance(content, Iterable) and not isinstance(content, dict):

        async def _read_iterable_async():
            for chunk in content:
                yield chunk

        return _read_iterable_async()

    if isinstance(content, Readable):

        async def _read_reader_async():
            while chunk := content.read(_CHUNK_SIZE):
                yield chunk

        return _read_reader_async()
    return content


def _validate_method(method: str):
    method = method.upper()
    if method not in _ALLOWED_METHODS:
        raise ApiValueError(f"Method {method} is not supported.")
    return method


def _interpolate_resource_path(
    resource_path: str,
    path_params: Mapping[str, str] | None = None,
):
    if not path_params:
        return resource_path
    for k, v in path_params.items():
        # specified safe chars, encode everything
        resource_path = resource_path.replace("{%s}" % k, quote(str(v)))
    return resource_path


def _deserialize(data: Any, klass: Any):
    """Deserializes response content into a `klass` instance."""
    if isinstance(klass, str) and klass in _CLASS_MAPPING:
        klass = _CLASS_MAPPING[klass]
    config = (
        ConfigDict(arbitrary_types_allowed=True)
        if not isclass(klass) or not issubclass(klass, BaseModel)
        else None
    )
    type_adapter = TypeAdapter(klass, config=config)
    try:
        return type_adapter.validate_python(data)
    except (TypeError, ValidationError) as exc:
        try:
            _deserialized = type_adapter.validate_python(
                data, strict=False, context={"skip_validation": True}
            )
            log.warning(
                "Failed to deserialize response into class %s, "
                "using backup non-validating deserializer instead.",
                klass,
                exc_info=exc,
                extra={"data": data, "class": klass},
            )
            return _deserialized
        except (TypeError, ValidationError):
            try:
                _deserialized = _MODEL_TYPE_ADAPTER.validate_python(data)
                log.warning(
                    "Failed to deserialize response into class %s, "
                    "using backup generic model deserializer instead.",
                    klass,
                    exc_info=exc,
                    extra={"data": data, "class": klass},
                )
                return _deserialized
            except (TypeError, ValidationError) as exc2:
                log.warning(
                    "Failed to deserialize response as a generic Model, "
                    "returning original data.",
                    exc_info=exc2,
                )
                return data


def _response_type_for_status_code(
    status_code,
    response_type: TypeMapping,
):
    status_code_key = str(status_code)
    rt_map = (
        {"2XX": response_type} if not isinstance(response_type, dict) else response_type
    )
    if rt_map is None:
        return _DEFAULT_RESPONSE_TYPE
    for key in [status_code_key, f"{status_code_key[0]}XX", "default", "*"]:
        rt = rt_map.get(key)
        if rt is not None:
            return rt
    return _DEFAULT_RESPONSE_TYPE


def _extract_selected(data, select_path: str):
    if not select_path:
        return data
    jsonpath_expr = jsonpath_parse(select_path)
    match_values = [match.value for match in jsonpath_expr.find(data)]
    data = (
        match_values[0]
        if not re.search(r"\[(\*|.*:.*|.*,.*)\]", select_path)
        else match_values
    )
    return data


T = TypeVar("T")


def _deserialize_response(
    response: Response,
    response_type: type[T],
    select_path: str = "",
) -> T:
    return_data: T = None  # type: ignore
    try:
        if response_type in _PRIMITIVE_BYTE_TYPES + tuple(
            t.__name__ for t in _PRIMITIVE_BYTE_TYPES
        ):
            _content = response.content
            try:
                return_data = cast(T, _content)
            except (TypeError, ValueError):
                return_data = _content  # type: ignore
        elif response_type is not None:
            try:
                _data = response.json()
                if select_path:
                    _data = _extract_selected(_data, select_path)
            except ValueError:
                _data = response.text
            if _data is not None:
                try:
                    return_data = _deserialize(_data, response_type)
                except (TypeError, ValueError):
                    return _data
            else:
                return_data = response.content  # type: ignore
        elif response_type is None:
            return_data = None
    except ResponseNotRead as exc:
        raise RestResponseError(
            "Cannot deserialize streaming response as object.", response=response
        ) from exc
    return return_data


async def _iter_event_stream(
    response: Response,
    response_type: type[T],
    select_path: str = "",
    *,
    _ignore_retry_events: bool = True,
) -> AsyncIterator[T]:
    _response_type = _response_type_for_status_code(response.status_code, response_type)
    content_type = response.headers.get("content-type", "")
    try:
        async for event_str in __iter_events_response(response, content_type):
            event = __parse_event(event_str, content_type)
            if not event:
                continue
            if _ignore_retry_events and "retry" in event and len(event) == 1:
                continue
            _deserialized_event = _deserialize(
                _extract_selected(event, select_path), _response_type
            )
            yield _deserialized_event
    finally:
        await response.aclose()


async def __iter_events_response(
    response: Response, content_type: str
) -> AsyncGenerator[str, None]:
    if content_type.startswith(TEXT_EVENT_STREAM_CONTENT_TYPE):
        async for event_str_batch in response.aiter_text():
            for event_str in event_str_batch.split("\r\n\r"):
                yield event_str
    else:
        async for event_str in response.aiter_lines():
            yield event_str


def __parse_event(event_str: str, content_type: str):
    if content_type.startswith(TEXT_EVENT_STREAM_CONTENT_TYPE):
        event = {}
        for line in event_str.split("\n"):
            keyword, *data = line.split(": ", 1)
            keyword = keyword.strip()
            _data = data[0].strip() if data else ""
            with contextlib.suppress(ValueError, TypeError):
                _data = json_lib.loads(_data)
            if keyword or data:
                event[keyword] = _data
        return event
    elif content_type == NDJSON_EVENT_STREAM_CONTENT_TYPE:
        try:
            event = json_lib.loads(event_str)
        except (ValueError, TypeError):
            log.warning("Cannot deserialize event\n%s", event_str, exc_info=True)
    else:
        return event_str
    return event
