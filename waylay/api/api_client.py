""" API client """

from importlib import import_module
from typing import Any, Dict, Optional, List

import datetime
from dateutil.parser import parse
import json
import mimetypes
import os
import re
import tempfile

from urllib.parse import quote

from waylay import __version__
from waylay.api.api_config import ApiConfig
from waylay.api.api_response import ApiResponse

from waylay.api import rest
from waylay.api.api_exceptions import (
    ApiValueError,
    ApiError,
)


class ApiClient:
    """Generic API client for OpenAPI client library builds.

    OpenAPI generic API client. This client handles the client-
    server communication, and is invariant across implementations. Specifics of
    the methods and models for each application are generated from the OpenAPI
    templates.

    :param configuration: configuration object for this client
    """

    PRIMITIVE_TYPES = (float, bool, bytes, str, int)
    NATIVE_TYPES_MAPPING = {
        'int': int,
        'float': float,
        'str': str,
        'bool': bool,
        'date': datetime.date,
        'datetime': datetime.datetime,
        'object': object,
    }
    _pool = None

    def __init__(
        self,
        configuration: ApiConfig,
    ) -> None:
        self.configuration = configuration
        self.rest_client = rest.RESTClient(configuration)
        self.default_headers = {}

        # Set default User-Agent.
        self.user_agent = "waylay-sdk/python/{__version__}"
        self.client_side_validation = configuration.client_side_validation

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @property
    def user_agent(self):
        """User agent for this API client"""
        return self.default_headers['User-Agent']

    @user_agent.setter
    def user_agent(self, value):
        self.default_headers['User-Agent'] = value

    def set_default_header(self, header_name, header_value):
        self.default_headers[header_name] = header_value

    def param_serialize(
        self,
        method: str,
        resource_path: str,
        path_params: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        header_params: Optional[Dict[str, Optional[str]]] = None,
        body: Optional[Any] = None,
        files: Dict[str, str] = None,
    ) -> Dict[str, Any]:

        """Builds the HTTP request params needed by the request.
        :param method: Method to call.
        :param resource_path: Path to method endpoint.
        :param path_params: Path parameters in the url.
        :param query_params: Query parameters in the url.
        :param header_params: Header parameters to be
            placed in the request header.
        :param body: Request body.
        :param files dict: key -> filename, value -> filepath,
            for `multipart/form-data`.
        :return: Dict of form {path, method, query_params, header_params, body, files}
        """

        config = self.configuration

        # header parameters
        header_params = header_params or {}
        header_params.update(self.default_headers)
        if header_params:
            header_params = self._sanitize_for_serialization(header_params)

        # path parameters
        if path_params:
            path_params = self._sanitize_for_serialization(path_params)

            for k, v in path_params.items():
                # specified safe chars, encode everything
                resource_path = resource_path.replace(
                    '{%s}' % k,
                    quote(str(v), safe=config.safe_chars_for_path_param)
                )

        # post parameters
        if files:
            files = self.files_parameters(files)

        # auth setting
        # TODO ??? 

        # body
        if body:
            body = self._sanitize_for_serialization(body)

        # request url
        url = self.configuration.host + resource_path

        # query parameters
        if query_params:
            query_params = self._sanitize_for_serialization(query_params)

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
        method,
        url,
        query_params: Optional[Dict[str, Any]] = None,
        header_params=None,
        body=None,
        files=None,
        _request_timeout=None
    ) -> rest.RESTResponse:
        """Makes the HTTP request (synchronous)
        :param method: Method to call.
        :param url: Path to method endpoint.
        :param query_params: Query parameters.
        :param header_params: Header parameters to be placed in the request header.
        :param body: Request body.
        :param files dict: Request files (`multipart/form-data`).
        :param _request_timeout: timeout setting for this request.
        :return: RESTResponse
        """

        try:
            # perform request and return response
            response_data = await self.rest_client.request(
                method, url, query=query_params,
                headers=header_params,
                body=body, files=files,
                _request_timeout=_request_timeout
            )

        except ApiError as e:
            if e.body:
                e.body = e.body.decode('utf-8')
            raise e

        return response_data

    def response_deserialize(
        self,
        response_data: rest.RESTResponse = None,
        response_types_map=None
    ) -> ApiResponse:
        """Deserializes response into an object.
        :param response_data: RESTResponse object to be deserialized.
        :param response_types_map: dict of response types.
        :return: ApiResponse
        """


        response_type = response_types_map.get(str(response_data.status_code), None)
        if not response_type and isinstance(response_data.status_code, int) and 100 <= response_data.status_code <= 599:
            # if not found, look for '1XX', '2XX', etc.
            response_type = response_types_map.get(str(response_data.status_code)[0] + "XX", None)

        # deserialize response data
        return_data = None
        try:
            if response_type == "bytearray":
                return_data = response_data.content
            elif response_type == "file":
                return_data = self.__deserialize_file(response_data)
            elif response_type is not None:
                return_data = self.deserialize(response_data, response_type)
        finally:
            if not 200 <= response_data.status_code <= 299:
                raise ApiError.from_response( # pylint: disable=raising-bad-type
                    http_resp=response_data,
                    content=response_data.content,
                    data=return_data,
                )

        return ApiResponse(
            status_code = response_data.status_code,
            data = return_data,
            headers = response_data.headers,
            raw_data = response_data.content
        )

    def _sanitize_for_serialization(self, obj):
        """Builds a JSON POST object.

        If obj is None, return None.
        If obj is str, int, long, float, bool, return directly.
        If obj is datetime.datetime, datetime.date
            convert to string in iso8601 format.
        If obj is list, sanitize each element in the list.
        If obj is dict, return the dict.
        If obj is OpenAPI model, return the properties dict.

        :param obj: The data to serialize.
        :return: The serialized form of data.
        """
        if obj is None:
            return None
        elif isinstance(obj, self.PRIMITIVE_TYPES):
            return obj
        elif isinstance(obj, list):
            return [
                self._sanitize_for_serialization(sub_obj) for sub_obj in obj
            ]
        elif isinstance(obj, tuple):
            return tuple(
                self._sanitize_for_serialization(sub_obj) for sub_obj in obj
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
            obj_dict = obj.to_dict()

        return {
            key: self._sanitize_for_serialization(val)
            for key, val in obj_dict.items()
        }

    def deserialize(self, response: rest.RESTResponse, response_type):
        """Deserializes response into an object.

        :param response: RESTResponse object to be deserialized.
        :param response_type: class literal for
            deserialized object, or string of class name.

        :return: deserialized object.
        """

        # fetch data from response object
        try:
            data = response.json()
        except ValueError:
            data = response.content

        return self.__deserialize(data, response_type)

    def __deserialize(self, data, klass):
        """Deserializes dict, list, str into an object.

        :param data: dict, list or str.
        :param klass: class literal, or string of class name.

        :return: object.
        """
        if data is None:
            return None

        if isinstance(klass, str):
            if klass.startswith('List['):
                sub_kls = re.match(r'List\[(.*)]', klass).group(1)
                return [self.__deserialize(sub_data, sub_kls)
                        for sub_data in data]

            if klass.startswith('Dict['):
                sub_kls = re.match(r'Dict\[([^,]*), (.*)]', klass).group(2)
                return {k: self.__deserialize(v, sub_kls)
                        for k, v in data.items()}

            # convert str to class
            if klass in self.NATIVE_TYPES_MAPPING:
                klass = self.NATIVE_TYPES_MAPPING[klass]
            else:
                try:
                    types_pkg_name, class_name = klass.split('.')
                    types_module = import_module(types_pkg_name)
                    klass = getattr(types_module, class_name)
                except:
                    klass = object

        if klass in self.PRIMITIVE_TYPES:
            return self.__deserialize_primitive(data, klass)
        elif klass == object:
            return self.__deserialize_object(data)
        elif klass == datetime.date:
            return self.__deserialize_date(data)
        elif klass == datetime.datetime:
            return self.__deserialize_datetime(data)
        else:
            return self.__deserialize_model(data, klass)

    def files_parameters(self, files=None):
        """Builds form parameters.

        :param files: File parameters.
        :return: Form parameters with files.
        """
        params = {}

        if files:
            for k, v in files.items():
                if not v:
                    continue
                file_names = v if type(v) is list else [v]
                for n in file_names:
                    with open(n, 'rb') as f:
                        filename = os.path.basename(f.name)
                        filedata = f.read()
                        mimetype = (
                            mimetypes.guess_type(filename)[0]
                            or 'application/octet-stream'
                        )
                        params[k] = tuple([filename, filedata, mimetype])

        return params

    def select_header_accept(self, accepts: List[str]) -> Optional[str]:
        """Returns `Accept` based on an array of accepts provided.

        :param accepts: List of headers.
        :return: Accept (e.g. application/json).
        """
        if not accepts:
            return None

        for accept in accepts:
            if re.search('json', accept, re.IGNORECASE):
                return accept

        return accepts[0]

    def select_header_content_type(self, content_types):
        """Returns `Content-Type` based on an array of content_types provided.

        :param content_types: List of content-types.
        :return: Content-Type (e.g. application/json).
        """
        if not content_types:
            return None

        for content_type in content_types:
            if re.search('json', content_type, re.IGNORECASE):
                return content_type

        return content_types[0]

    def __deserialize_file(self, response: rest.RESTResponse):
        """Deserializes body to file

        Saves response body into a file in a temporary folder,
        using the filename from the `Content-Disposition` header if provided.

        handle file downloading
        save response body into a tmp file and return the instance

        :param response:  RESTResponse.
        :return: file path.
        """
        fd, path = tempfile.mkstemp(dir=self.configuration.temp_folder_path)
        os.close(fd)
        os.remove(path)

        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition:
            filename = re.search(
                r'filename=[\'"]?([^\'"\s]+)[\'"]?',
                content_disposition
            ).group(1)
            path = os.path.join(os.path.dirname(path), filename)

        with open(path, "wb") as f:
            f.write(response.content)

        return path

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
        except ImportError:
            return string
        except ValueError:
            raise ApiError(
                status=0,
                reason="Failed to parse `{0}` as date object".format(string)
            )

    def __deserialize_datetime(self, string):
        """Deserializes string to datetime.

        The string should be in iso8601 datetime format.

        :param string: str.
        :return: datetime.
        """
        try:
            return parse(string)
        except ImportError:
            return string
        except ValueError:
            raise ApiError(
                status=0,
                reason=(
                    "Failed to parse `{0}` as datetime object"
                    .format(string)
                )
            )

    def __deserialize_model(self, data, klass):
        """Deserializes list or dict to model.

        :param data: dict, list.
        :param klass: class literal.
        :return: model object.
        """

        return klass.from_dict(data)
