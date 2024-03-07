"""API client."""

import logging
import re
import datetime
from urllib.parse import quote
from importlib import import_module
from inspect import isclass
from typing import Any, Mapping, Optional, cast, AsyncIterable
from io import BufferedReader
from abc import abstractmethod
import warnings

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from jsonpath_ng import parse as jsonpath_parse  # type: ignore[import-untyped]
from httpx import QueryParams

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
_REMOVE_NONE_DEFAULT = ["timeout"]
_REMOVE_FALSY_DEFAULT = ["params", "headers", "files"]

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
        params: Optional[QueryParamTypes] = None,
        json: Optional[Any] = None,
        content: Optional[RequestContent] = None,
        files: Optional[RequestFiles] = None,
        data: Optional[RequestData] = None,
        headers: Optional[HeaderTypes] = None,
        **kwargs,
    ) -> Request:
        """Build the HTTP request params needed by the request."""
        method = _validate_method(method)
        url = _interpolate_resource_path(resource_path, path_params)
        params = _sanitize_for_serialization(params)
        headers = _sanitize_for_serialization(headers)
        files = _sanitize_files_parameters(files)
        json = _sanitize_for_serialization(json)
        return self.http_client.build_request(
            method,
            url,
            params=params,
            json=json,
            content=content,
            files=files,
            data=data,
            headers=headers,
            **kwargs,
        )

    def build_api_request(
        self,
        method: str,
        resource_path: str,
        path_params: Optional[Mapping[str, str]] = None,
        query_params: Optional[Mapping[str, Any]] = None,
        body: Optional[Any] = None,
        files: Optional[RequestFiles] = None,
        headers: Optional[HeaderTypes] = None,
        **kwargs,
    ) -> Request:
        """Build the HTTP request params needed by the request.

        :param method: Method to call.
        :param resource_path: Path to method endpoint.
        :param path_params: Path parameters in the url.
        :param query_params: Query parameters in the url.

        :param body: Request body.
        :param files dict: key -> filename, value -> filepath, for
            `multipart/form-data`.
        :param headers: Header parameters to be placed in the
            request header.
        :param kwargs: Other options passed to the http client.
            See waylay.sdk.api.HttpClientOptions
        :return: Sanitized http call arguments of form {
            path, method, url, params, headers, body, files, *kwargs
            }

        """
        method = _validate_method(method)
        url = _interpolate_resource_path(resource_path, path_params)
        extra_params: Optional[QueryParamTypes] = kwargs.pop("params", None)
        request = {
            "params": build_params(query_params, extra_params),
            "headers": _sanitize_for_serialization(headers),
            "files": _sanitize_files_parameters(files),
            **kwargs,
        }
        for key in _REMOVE_NONE_DEFAULT:
            if key in request and request[key] is None:
                request.pop(key)
        for key in _REMOVE_FALSY_DEFAULT:
            if key in request and not request[key]:
                request.pop(key)
        if body:
            body = _sanitize_for_serialization(body)
            request.update(convert_body(body, request))
        return self.http_client.build_request(method, url, **request)

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
    api_params = cast(dict, _sanitize_for_serialization(api_params))
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


def _sanitize_for_serialization(obj):
    """Build a JSON POST object.

    If obj is None, return None.
    If obj is str, int, long, float, bool, return directly.
    If obj is datetime.datetime, datetime.date convert to string in iso8601 format.
    If obj is list, sanitize each element in the list.
    If obj is dict, return the dict.
    If obj is OpenAPI model, return the properties dict.

    :param obj: The data to serialize.
    :return: The serialized form of data.
    """
    if obj is None:
        return None
    elif isinstance(obj, _PRIMITIVE_TYPES + _PRIMITIVE_BYTE_TYPES):
        return obj
    elif isinstance(obj, list):
        return [_sanitize_for_serialization(sub_obj) for sub_obj in obj]
    elif isinstance(obj, tuple):
        return tuple(_sanitize_for_serialization(sub_obj) for sub_obj in obj)
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()

    elif isinstance(obj, dict):
        obj_dict = obj
    else:
        # Convert model obj to dict except
        # attributes `openapi_types`, `attribute_map`
        # and attributes which value is not None.
        # Convert attribute name to json key in
        # model definition for request.
        try:
            obj_dict = obj.to_dict()
        except AttributeError:
            return obj

    return {key: _sanitize_for_serialization(val) for key, val in obj_dict.items()}


def _deserialize(data: Any, klass: Any):
    """Deserializes response content into a `klass` instance."""
    if isinstance(klass, str) and klass in _CLASS_MAPPING:
        klass = _CLASS_MAPPING[klass]
    elif isinstance(klass, str):
        if klass.startswith("List["):
            inner_kls = re.match(r"List\[(.*)]", klass).group(1)  # type: ignore[union-attr]
            return [_deserialize(sub_data, inner_kls) for sub_data in data]
        elif klass.startswith("Dict["):
            match = re.match(r"Dict\[([^,]*), (.*)]", klass)
            (key_kls, val_kls) = (match.group(1), match.group(2))  # type: ignore[union-attr]
            return {
                _deserialize(k, key_kls): _deserialize(v, val_kls)
                for k, v in data.items()
            }
        elif "." in klass:
            try:
                # get the actual class from the class name
                [types_module_name, class_name] = klass.rsplit(".", 1)
                types_module = import_module(types_module_name)
                klass = getattr(types_module, class_name)
            except (AttributeError, ValueError, TypeError, ImportError):
                return _MODEL_TYPE_ADAPTER.validate_python(data)

    config = (
        ConfigDict(arbitrary_types_allowed=True)
        if isclass(klass) and not issubclass(klass, BaseModel)
        else None
    )
    klass_type_adapter = TypeAdapter(klass, config=config)
    try:
        return klass_type_adapter.validate_python(data)
    except ValidationError as exc:
        log.warning(
            "Failed to deserialize response into class %s, using backup deserializer instead.",
            klass,
            exc_info=exc,
            extra={"data": data, "class": klass},
        )
        return _MODEL_TYPE_ADAPTER.validate_python(data)


def _sanitize_files_parameters(files=Optional[RequestFiles]):
    """Build form parameters.

    :param files: File parameters.
    :return: Form parameters with files.

    """
    return files
