"""API client."""

import logging
import re
import datetime
from urllib.parse import quote
from inspect import isclass
from typing import Any, Mapping, Optional, cast, AsyncIterable, Union
from io import BufferedReader
from abc import abstractmethod
import warnings

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from pydantic_core import to_jsonable_python
from jsonpath_ng import parse as jsonpath_parse  # type: ignore[import-untyped]
from httpx import QueryParams, USE_CLIENT_DEFAULT
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
_PRIMITIVE_TYPES = (float, bool, str, int)
_CLASS_MAPPING = {
    "date": datetime.date,
    "datetime": datetime.datetime,
    "Any": Any,
}
_ALLOWED_METHODS = ["GET", "HEAD", "DELETE", "POST", "PUT", "PATCH", "OPTIONS"]

_MODEL_TYPE_ADAPTER = TypeAdapter(Model)

log = logging.getLogger(__name__)


class WithSerializationSupport:
    """Serialization support for the SDK client."""

    base_url: str

    @property
    @abstractmethod
    def http_client(self) -> AsyncClient:
        """Get (or open) a http client."""

    def build_request(
        self,
        method: str,
        resource_path: str,
        path_params: Optional[Mapping[str, str]] = None,
        *,
        params: Optional[Union[QueryParamTypes, Mapping]] = None,
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
        params = to_jsonable_python(params, by_alias=True)
        json = to_jsonable_python(json, by_alias=True)
        data = to_jsonable_python(data, by_alias=True)
        return self.http_client.build_request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=USE_CLIENT_DEFAULT if timeout is None else timeout,
            extensions=extensions,
        )

    def response_deserialize(
        self,
        response: Response,
        response_types_map=None,
        select_path: str = "",
        stream: bool = False,
    ) -> Any:
        """Deserialize response into a model object.

        :param response_data: Response object to be deserialized.
        :param response_types_map: dict of response types.
        :param select_path: json path into the json payload.
        :return: The response model
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
                            if not re.search(r"\[.*\]", select_path)
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


def build_params(
    api_params: Optional[Mapping[str, Any]], extra_params: Optional[QueryParamTypes]
) -> Optional[QueryParamTypes]:
    """Sanitize and merge parameters."""
    api_params = cast(dict, to_jsonable_python(api_params, by_alias=True))
    if not api_params:
        return extra_params
    if not extra_params:
        return api_params
    # merge parameters
    return QueryParams(api_params).merge(extra_params)


def convert_body(
    body: Any,
    kwargs,
) -> Mapping[str, Any]:
    """SDK invocation request with untyped body."""
    headers = kwargs.pop("headers", None) or {}
    content_type = headers.get("content-type", "").lower()
    if isinstance(body, BufferedReader):

        async def read_buffer():
            while chunk := body.read(_CHUNK_SIZE):
                yield chunk

        kwargs["content"] = read_buffer()
    elif isinstance(body, (bytes, AsyncIterable)):
        kwargs["content"] = body
    elif content_type.startswith("application/x-www-form-urlencoded"):
        kwargs["data"] = body
    elif not content_type:
        # TBD: check string case
        # body='"abc"', content-type:'application/json' => content='"abc"'
        # body='abc' => json='abc' (encoded '"abc"')
        # body='abc', content-type:'application/json' => content='abc' (invalid)
        kwargs["json"] = body
    else:
        kwargs["content"] = body
    if "content" in kwargs and not content_type:
        headers["content-type"] = "application/octet-stream"
    kwargs["headers"] = headers
    return kwargs


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
        if isclass(klass) and not issubclass(klass, BaseModel)
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
