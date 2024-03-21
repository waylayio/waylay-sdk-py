"""API client."""

from __future__ import annotations
import logging
import re
import datetime
from urllib.parse import quote
from inspect import isclass
from typing import (
    Any,
    Mapping,
    Optional,
    AsyncIterable,
    Type,
    Union,
    Iterable,
    Protocol,
    runtime_checkable,
)
from abc import abstractmethod
import warnings

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from pydantic_core import to_jsonable_python
from jsonpath_ng import parse as jsonpath_parse  # type: ignore[import-untyped]
from httpx import USE_CLIENT_DEFAULT
import httpx._client as httpxc

from .http import (
    AsyncClient,
    Request,
    Response,
    QueryParamTypes,
    HeaderTypes,
    RequestFiles,
    RequestContent,
    RequestData,
)
from .exceptions import ApiValueError, ApiError
from ._models import Model


_PRIMITIVE_BYTE_TYPES = (bytes, bytearray)
_CLASS_MAPPING = {
    "date": datetime.date,
    "datetime": datetime.datetime,
    "Any": Any,
}
_ALLOWED_METHODS = ["GET", "HEAD", "DELETE", "POST", "PUT", "PATCH", "OPTIONS"]

_MODEL_TYPE_ADAPTER = TypeAdapter(Model)

log = logging.getLogger(__name__)

DEFAULT_SERIALIZATION_ARGS = {"by_alias": True, "exclude_none": True}


class WithSerializationSupport:
    """Serialization support for the SDK client."""

    base_url: str
    serialization_args = DEFAULT_SERIALIZATION_ARGS

    @property
    @abstractmethod
    def http_client(self) -> AsyncClient:
        """Get (or open) a http client."""

    async def request(
        self,
        method: str,
        resource_path: str,
        path_params: Optional[Mapping[str, str]] = None,
        *,
        params: Optional[Union[QueryParamTypes, Mapping, BaseModel]] = None,
        json: Optional[Any] = None,
        content: Optional[RequestContent] = None,
        files: Optional[RequestFiles] = None,
        data: Optional[RequestData] = None,
        headers: Optional[HeaderTypes] = None,
        cookies: httpxc.CookieTypes | None = None,
        timeout: httpxc.TimeoutTypes | None = None,
        extensions: httpxc.RequestExtensions | None = None,
        # Deserialization arguments
        response_types_map: Mapping[str, Type | None] | None = None,
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
            response_types_map,
            select_path,
            stream=send_args.get("stream", False),
        )

    def build_request(
        self,
        method: str,
        resource_path: str,
        path_params: Optional[Mapping[str, str]] = None,
        *,
        params: Optional[Union[QueryParamTypes, Mapping, BaseModel]] = None,
        json: Optional[Any] = None,
        content: Optional[RequestContent] = None,
        files: Optional[RequestFiles] = None,
        data: Optional[RequestData] = None,
        headers: Optional[HeaderTypes] = None,
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
        return to_jsonable_python(data, **self.serialization_args)

    def deserialize(
        self,
        response: Response,
        response_types_map: Mapping[str, Type | None] | None = None,
        select_path: str = "",
        stream: bool = False,
    ) -> Any:
        """Deserialize a http response into a python object.

        :param response_data: Response object to be deserialized.
        :param response_types_map: A mapping of response types per status code: examples [{"200": Model}, {"2XX": Model}, {"*": Model}]
        :param select_path: json path to be extracted from the json payload.
        :return: An instance of the type specified in the mapping.
        """
        if stream:
            warnings.warn(
                "Using `stream=True` is currently only supported with `raw_response=True`."
            )
            return response
        status_code = response.status_code
        status_code_key = str(status_code)
        response_types_map = response_types_map or {}
        response_type = response_types_map.get(status_code_key, None)
        if (
            not response_type
            and isinstance(status_code, int)
            and 100 <= response.status_code <= 599
        ):
            # if not found, look for '1XX', '2XX', etc.
            response_type = response_types_map.get(status_code_key[0] + "XX")
        if not response_type:
            # if still not found, look for default response type, otherwise use `Model`
            response_type = (
                response_types_map.get("*")
                or response_types_map.get("default")
                or Model
            )

        # deserialize response data
        return_data = None
        try:
            if response_type in _PRIMITIVE_BYTE_TYPES + tuple(
                t.__name__ for t in _PRIMITIVE_BYTE_TYPES
            ):
                return_data = response.content
            elif response_type is not None:
                try:
                    _data = response.json()
                    if select_path:
                        jsonpath_expr = jsonpath_parse(select_path)
                        match_values = [
                            match.value for match in jsonpath_expr.find(_data)
                        ]
                        _data = (
                            match_values[0]
                            if not re.search(r"\[(\*|.*:.*|.*,.*)\]", select_path)
                            else match_values
                        )
                except ValueError:
                    _data = response.text
                if _data is not None:
                    return_data = _deserialize(_data, response_type)
                else:
                    return_data = response.content
        finally:
            if not 200 <= status_code <= 299:
                raise ApiError.from_response(
                    response,
                    return_data,
                )
        return return_data


_CHUNK_SIZE = 65_536


@runtime_checkable
class Readable(Protocol):
    """Anything with a binary read method."""

    def read(self, n: int = -1) -> bytes:
        """Read a binary chunk"""


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
    path_params: Optional[Mapping[str, str]] = None,
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
            _deserialized = _MODEL_TYPE_ADAPTER.validate_python(data)
            log.warning(
                "Failed to deserialize response into class %s, using backup deserializer instead.",
                klass,
                exc_info=exc,
                extra={"data": data, "class": klass},
            )
            return _deserialized
        except (TypeError, ValidationError) as exc2:
            log.warning(
                "Failed to deserialize response as a generic Model, returning original data.",
                exc_info=exc2,
            )
            return data
