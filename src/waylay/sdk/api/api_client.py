"""API client."""

from enum import Enum
from importlib import import_module
from inspect import isclass
from types import SimpleNamespace
from typing import Any, Mapping, Optional, cast

import datetime
from dateutil.parser import parse
import re
from urllib.parse import quote

from ..__version__ import __version__
from ..config import WaylayConfig

from ..api import rest
from .api_config import ApiConfig
from .api_response import ApiResponse
from .api_exceptions import (
    ApiError,
)

_PRIMITIVE_BYTE_TYPES = (bytes, bytearray)
_PRIMITIVE_TYPES = (float, bool, str, int)
_NATIVE_TYPES_MAPPING = {
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'date': datetime.date,
    'datetime': datetime.datetime,
    'object': object,
}


class ApiClient:
    """Generic API client for OpenAPI client library builds.

    OpenAPI generic API client. This client handles the client- server
    communication, and is invariant across implementations. Specifics of
    the methods and models for each application are generated from the
    OpenAPI templates.

    :param configuration: configuration object for this client

    """

    def __init__(
        self,
        waylay_config: WaylayConfig,
    ) -> None:
        """Create an instance."""
        self.config = ApiConfig(waylay_config)

        rest_client_kwargs = {"auth": waylay_config.auth}
        rest_client_kwargs.update(self.config._client_options or {})
        self.rest_client = rest.RESTClient(**rest_client_kwargs)

        self.default_headers: dict[str, Any] = {
            'User-Agent': "waylay-sdk/python/{0}".format(__version__)
        }

    def param_serialize(
        self,
        method: str,
        resource_path: str,
        path_params: Optional[Mapping[str, str]] = None,
        query_params: Optional[Mapping[str, Any]] = None,
        header_params: Optional[Mapping[str, Optional[str]]] = None,
        body: Optional[Any] = None,
        files: Optional[Mapping[str, str]] = None,
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
        :return: dict of form {path, method, query_params,
            header_params, body, files}

        """

        # header parameters
        header_params = dict(header_params or {})
        header_params.update(self.default_headers)
        if header_params:
            header_params = {k.lower(): v for k, v in header_params.items()}
            header_params = self.__sanitize_for_serialization(header_params)

        # path parameters
        if path_params:
            path_params = self.__sanitize_for_serialization(path_params)

            for k, v in path_params.items() if path_params else []:
                # specified safe chars, encode everything
                resource_path = resource_path.replace(
                    '{%s}' % k,
                    quote(str(v))
                )

        # post parameters
        if files:
            files = self.__sanitize_files_parameters(files)

        if body:
            body = self.__sanitize_for_serialization(body)

        # request url
        url = self.config.host + resource_path

        # query parameters
        if query_params:
            query_params = self.__sanitize_for_serialization(query_params)

        return {
            'method': method,
            'url': url,
            'query_params': query_params,
            'header_params': header_params,
            'body': body,
            'files': files
        }

    async def call_api(
        self,
        method: str,
        url: str,
        query_params: Optional[Mapping[str, Any]] = None,
        header_params: Optional[Mapping[str, str]] = None,
        body: Optional[Any] = None,
        files: Optional[Mapping[str, str]] = None,
        _request_timeout: Optional[rest.RESTTimeout] = None
    ) -> rest.RESTResponse:
        """Make the HTTP request (synchronous) :param method: Method to call.

        :param url: Path to method endpoint.
        :param query_params: Query parameters.
        :param header_params: Header parameters to be placed in the
            request header.
        :param body: Request body.
        :param files dict: Request files (`multipart/form-data`).
        :param _request_timeout: timeout setting for this request.
        :return: RESTResponse

        """
        # perform request and return response
        response_data = await self.rest_client.request(
            method, url, query=query_params,
            headers=header_params,
            body=body, files=files,
            _request_timeout=_request_timeout
        )
        return response_data

    def response_deserialize(
        self,
        response_data: rest.RESTResponse,
        response_types_map=None,
    ) -> ApiResponse:
        """Deserialize response into an object.

        :param response_data: RESTResponse object to be deserialized.
        :param response_types_map: dict of response types.
        :return: ApiResponse

        """

        response_type = response_types_map.get(str(response_data.status_code), None)
        if not response_type and isinstance(response_data.status_code, int) and 100 <= response_data.status_code <= 599:
            # if not found, look for '1XX', '2XX', etc.
            response_type = response_types_map.get(str(response_data.status_code)[0] + "XX")
        if not response_type:
            # if still not found, look for default response type, otherwise use `Any`
            response_type = response_types_map.get('*') or response_types_map.get('default') or Any

        # deserialize response data
        return_data = None
        try:
            if response_type in _PRIMITIVE_BYTE_TYPES + tuple(t.__name__ for t in _PRIMITIVE_BYTE_TYPES):
                return_data = response_data.content
            elif response_type is not None:
                try:
                    _data = response_data.json()
                except ValueError:
                    _data = response_data.text
                return_data = self.__deserialize(_data, response_type) if _data is not None else response_data.content
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
            raw_data=response_data.content
        )

    def __sanitize_for_serialization(self, obj):
        """Build a JSON POST object.

        If obj is None, return None. If obj is str, int, long, float,
        bool, return directly. If obj is datetime.datetime,
        datetime.date     convert to string in iso8601 format. If obj is
        list, sanitize each element in the list. If obj is dict, return
        the dict. If obj is OpenAPI model, return the properties dict.

        :param obj: The data to serialize.
        :return: The serialized form of data.

        """
        if obj is None:
            return None
        elif isinstance(obj, _PRIMITIVE_TYPES + _PRIMITIVE_BYTE_TYPES):
            return obj
        elif isinstance(obj, list):
            return [
                self.__sanitize_for_serialization(sub_obj) for sub_obj in obj
            ]
        elif isinstance(obj, tuple):
            return tuple(
                self.__sanitize_for_serialization(sub_obj) for sub_obj in obj
            )
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

        return {
            key: self.__sanitize_for_serialization(val)
            for key, val in obj_dict.items()
        }

    def __deserialize(self, data: Any, klass: Any):
        """Deserializes response content into a `klass` instance."""
        if isinstance(klass, str) and klass in _NATIVE_TYPES_MAPPING:
            # if the response_type is string representing primitive type, replace it with the actual primitive class
            klass = _NATIVE_TYPES_MAPPING[klass]
            # continue
        if klass in _PRIMITIVE_TYPES + _PRIMITIVE_BYTE_TYPES:
            return self.__deserialize_primitive(data, klass)
        elif klass == object:
            return self.__deserialize_object(data)
        elif klass == datetime.date:
            return self.__deserialize_date(data)
        elif klass == datetime.datetime:
            return self.__deserialize_datetime(data)
        if isinstance(klass, str):
            if klass.startswith('List['):
                sub_kls = re.match(r'List\[(.*)]', klass).group(1)  # type: ignore[union-attr]
                return [self.__deserialize(sub_data, sub_kls)
                        for sub_data in data]

            if klass.startswith('Dict['):
                sub_kls = re.match(r'Dict\[([^,]*), (.*)]', klass).group(2)  # type: ignore[union-attr]
                return {k: self.__deserialize(v, sub_kls)
                        for k, v in data.items()}

            else:
                try:
                    # get the actual class from the class name
                    [types_module_name, class_name] = klass.rsplit('.', 1)
                    types_module = import_module(types_module_name)
                    klass = getattr(types_module, class_name)
                    # continue
                except BaseException:
                    return self.__deserialize_simple_namespace(data)
        if isclass(klass) and issubclass(klass, Enum):
            return self.__deserialize_enum(data, klass)
        else:
            return self.__deserialize_model(data, klass)

    def __sanitize_files_parameters(self, files=None):
        """Build form parameters.

        :param files: File parameters.
        :return: Form parameters with files.

        """

        return files

    def __deserialize_primitive(self, data, klass):
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

    def __deserialize_object(self, value):
        """Return an original value.

        :return: object.

        """
        return value

    def __deserialize_date(self, string):
        """Deserializes string to date.

        :param string: str.
        :return: date.

        """
        try:
            return parse(string).date()
        except ValueError:
            return string

    def __deserialize_datetime(self, string):
        """Deserializes string to datetime.

        The string should be in iso8601 datetime format.

        :param string: str.
        :return: datetime.

        """
        try:
            return parse(string)
        except ValueError:
            return string

    def __deserialize_enum(self, data, klass):
        """Deserializes primitive type to enum.

        :param data: primitive type.
        :param klass: class literal.
        :return: enum value.

        """
        try:
            return klass(data)
        except ValueError:
            raise ApiError(
                status=0,
                reason=(
                    "Failed to parse `{0}` as `{1}`"
                    .format(data, klass)
                )
            )

    def __deserialize_model(self, data, klass):
        """Deserializes list or dict to model.

        :param data: dict, list.
        :param klass: class literal.
        :return: model object.

        """

        try:
            if callable(getattr(klass, 'from_dict', None)):
                return klass.from_dict(data)
        except BaseException as e:
            pass
        return self.__deserialize_simple_namespace(data)

    def __deserialize_simple_namespace(self, data):
        """Deserializes dict to a `SimpleNamespace`.

        :param data: str.
        :return: SimpleNamespace.

        """
        if isinstance(data, list):
            return list(map(self.__deserialize_simple_namespace, data))
        elif isinstance(data, dict):
            sns = SimpleNamespace()
            for key, value in data.items():
                setattr(sns, key, self.__deserialize_simple_namespace(value))
            return sns
        else:
            return data
