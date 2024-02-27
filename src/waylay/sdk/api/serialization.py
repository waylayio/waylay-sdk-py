"""API client."""
import re
import datetime
from urllib.parse import quote
from enum import Enum
from importlib import import_module
from inspect import isclass
from types import SimpleNamespace
from typing import Any, Mapping, Optional, cast

from dateutil.parser import parse

from .response import ApiResponse
from .http import Response as RESTResponse
from .exceptions import ApiValueError, ApiError

_PRIMITIVE_BYTE_TYPES = (bytes, bytearray)
_PRIMITIVE_TYPES = (float, bool, str, int)
_NATIVE_TYPES_MAPPING = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "date": datetime.date,
    "datetime": datetime.datetime,
    "object": object,
}


class WithSerializationSupport:
    """Serialization support for the SDK client."""

    base_url: str

    def param_serialize(
        self,
        method: str,
        resource_path: str,
        path_params: Optional[Mapping[str, str]] = None,
        query_params: Optional[Mapping[str, Any]] = None,
        header_params: Optional[Mapping[str, Optional[str]]] = None,
        body: Optional[Any] = None,
        files: Optional[Mapping[str, str]] = None,
        base_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build the HTTP request params needed by the request.

        :param method: Method to call.
        :param resource_path: Path to method endpoint.
        :param path_params: Path parameters in the url.
        :param query_params: Query parameters in the url.
        :param header_params: Header parameters to be placed in the
            request header.
        :param body: Request body.
        :param files dict: key -> filename, value -> filepath, for
            `multipart/form-data`.
        :base_url: the host url to use
        :return: dict of form {path, method, query_params,
            header_params, body, files}

        """

        # header parameters
        header_params = dict(header_params or {})
        if header_params:
            header_params = {k.lower(): v for k, v in header_params.items()}
            header_params = _sanitize_for_serialization(header_params)

        # path parameters
        if path_params:
            path_params = _sanitize_for_serialization(path_params)

            for k, v in path_params.items() if path_params else []:
                # specified safe chars, encode everything
                resource_path = resource_path.replace("{%s}" % k, quote(str(v)))

        # post parameters
        if files:
            files = _sanitize_files_parameters(files)

        if body:
            body = _sanitize_for_serialization(body)

        # request url
        url = (base_url or self.base_url) + resource_path

        # query parameters
        if query_params:
            query_params = _sanitize_for_serialization(query_params)

        return {
            "method": method,
            "url": url,
            "query_params": query_params,
            "header_params": header_params,
            "body": body,
            "files": files,
        }

    def response_deserialize(
        self,
        response_data: RESTResponse,
        response_types_map=None,
    ) -> ApiResponse:
        """Deserialize response into an object.

        :param response_data: RESTResponse object to be deserialized.
        :param response_types_map: dict of response types.
        :return: ApiResponse
        """

        response_type = response_types_map.get(str(response_data.status_code), None)
        if (
            not response_type
            and isinstance(response_data.status_code, int)
            and 100 <= response_data.status_code <= 599
        ):
            # if not found, look for '1XX', '2XX', etc.
            response_type = response_types_map.get(
                str(response_data.status_code)[0] + "XX"
            )
        if not response_type:
            # if still not found, look for default response type, otherwise use `Any`
            response_type = (
                response_types_map.get("*") or response_types_map.get("default") or Any
            )

        # deserialize response data
        return_data = None
        try:
            if response_type in _PRIMITIVE_BYTE_TYPES + tuple(
                t.__name__ for t in _PRIMITIVE_BYTE_TYPES
            ):
                return_data = response_data.content
            elif response_type is not None:
                try:
                    _data = response_data.json()
                except ValueError:
                    _data = response_data.text
                return_data = (
                    _deserialize(_data, response_type)
                    if _data is not None
                    else response_data.content
                )
        finally:
            if not 200 <= response_data.status_code <= 299:
                raise ApiError.from_response(  # pylint: disable=raising-bad-type
                    http_resp=response_data,
                    content=response_data.content,
                    data=return_data,
                )

        return ApiResponse(
            status_code=response_data.status_code,
            data=return_data,
            headers=cast(dict[str, str], response_data.headers),
            raw_data=response_data.content,
        )


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
    if isinstance(klass, str) and klass in _NATIVE_TYPES_MAPPING:
        # if the response_type is string representing primitive type, replace it with the actual primitive class
        klass = _NATIVE_TYPES_MAPPING[klass]
    if klass in _PRIMITIVE_TYPES + _PRIMITIVE_BYTE_TYPES:
        return __deserialize_primitive(data, klass)
    elif klass == object:
        return __deserialize_object(data)
    elif klass == datetime.date:
        return __deserialize_date(data)
    elif klass == datetime.datetime:
        return __deserialize_datetime(data)
    if isinstance(klass, str):
        if klass.startswith("List["):
            sub_kls = re.match(r"List\[(.*)]", klass).group(1)  # type: ignore[union-attr]
            return [_deserialize(sub_data, sub_kls) for sub_data in data]

        if klass.startswith("Dict["):
            sub_kls = re.match(r"Dict\[([^,]*), (.*)]", klass).group(2)  # type: ignore[union-attr]
            return {k: _deserialize(v, sub_kls) for k, v in data.items()}

        else:
            try:
                # get the actual class from the class name
                [types_module_name, class_name] = klass.rsplit(".", 1)
                types_module = import_module(types_module_name)
                klass = getattr(types_module, class_name)
            except (AttributeError, ValueError, TypeError, ImportError):
                return __deserialize_simple_namespace(data)

    if isclass(klass) and issubclass(klass, Enum):
        return __deserialize_enum(data, klass)
    else:
        return __deserialize_model(data, klass)


def _sanitize_files_parameters(files=None):
    """Build form parameters.

    :param files: File parameters.
    :return: Form parameters with files.

    """

    return files


def __deserialize_primitive(data, klass):
    """Deserializes string to primitive type.

    :param data: str.
    :param klass: class literal.
    :return: int, long, float, str, bool.

    """
    try:
        return klass(data)
    except UnicodeEncodeError:
        return str(data)
    except TypeError:
        return data


def __deserialize_object(value):
    """Return an original value.

    :return: object.

    """
    return value


def __deserialize_date(string):
    """Deserializes string to date.

    :param string: str.
    :return: date.

    """
    try:
        return parse(string).date()
    except ValueError:
        return string


def __deserialize_datetime(string):
    """Deserializes string to datetime.

    The string should be in iso8601 datetime format.

    :param string: str.
    :return: datetime.

    """
    try:
        return parse(string)
    except ValueError:
        return string


def __deserialize_enum(data, klass):
    """Deserializes primitive type to enum.

    :param data: primitive type.
    :param klass: class literal.
    :return: enum value.

    """
    try:
        return klass(data)
    except ValueError as exc:
        raise ApiValueError(f"Failed to parse `{data}` as `{klass}`") from exc


def __deserialize_model(data, klass):
    """Deserializes list or dict to model.

    :param data: dict, list.
    :param klass: class literal.
    :return: model object.

    """
    if callable(getattr(klass, "from_dict", None)):
        try:
            return klass.from_dict(data)
        except (ValueError, TypeError):
            pass
    return __deserialize_simple_namespace(data)


def __deserialize_simple_namespace(data):
    """Deserializes dict to a `SimpleNamespace`.

    :param data: str.
    :return: SimpleNamespace.

    """
    if isinstance(data, list):
        return list(map(__deserialize_simple_namespace, data))
    elif isinstance(data, dict):
        sns = SimpleNamespace()
        for key, value in data.items():
            setattr(sns, key, __deserialize_simple_namespace(value))
        return sns
    else:
        return data
