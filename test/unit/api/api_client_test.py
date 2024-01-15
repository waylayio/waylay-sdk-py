"""Test suite for package `waylay.api`."""

import re
from typing import Any, Dict, List, Union
from unittest import mock
from urllib import parse
import httpx
import pytest
from datetime import datetime, date

from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from waylay.auth import TokenCredentials
from waylay.config import WaylayConfig
from waylay.api import ApiConfig, ApiClient
from waylay.api.rest import RESTResponse
from waylay.api.api_exceptions import ApiError, ApiValueError

from ..fixtures import WaylayTokenStub
from .example.pet_model import Pet
from .example.pet_fixtures import pet_instance, pet_instance_dict, pet_instance_json


@pytest.fixture
def waylay_token_credentials() -> TokenCredentials:
    return TokenCredentials(token='dummy_token', gateway_url='https://api-example.io')


@pytest.fixture
def waylay_config(waylay_token_credentials: TokenCredentials) -> WaylayConfig:
    return WaylayConfig(credentials=waylay_token_credentials)


@pytest.fixture
def waylay_api_config(waylay_config: WaylayConfig) -> ApiConfig:
    return ApiConfig(waylay_config)


@pytest.fixture
def waylay_api_client(waylay_api_config: ApiConfig) -> ApiClient:
    return ApiClient(waylay_api_config)


@pytest.mark.parametrize("test_input",
                         [{'method': 'GET',
                           'resource_path': '/service/v1/{param1}/foo/{param2}',
                           'path_params': {'param1': 'A',
                                           'param2': 'B'},
                             'query_params': {'key1': 'value1',
                                              'key2': 'value2'},
                             'header_params': {'x-my-header': 'header_value'},
                             'body': None,
                             'files': None,
                           },
                             {'method': 'PATCH',
                              'resource_path': '/service/v1/{param1}/bar/{missing_param}',
                              'path_params': {'param1': 'A',
                                              'param_not_in_resource_path': 'B'},
                              'query_params': None,
                              'header_params': {'x-my-header': 'header_value'},
                              'body': {'array_key': ['val1',
                                                     'val2'],
                                       'tuple_key': ('val3',
                                                     123,
                                                     {'key': 'value'},
                                                     None),
                                       'timestamp': datetime(1999,
                                                             9,
                                                             28,
                                                             hour=12,
                                                             minute=30,
                                                             second=59)},
                              },
                             {'method': 'POST',
                              'resource_path': '/service/v1/cruz/',
                              'path_params': None,
                              'query_params': {'key1': 15},
                              'files': {'file1': b'<... binary content ...>',
                                        'file2': '<... other binary content ...>'},
                              },
                             {'method': 'PUT',
                              'resource_path': '/service/v1/{param1}/foo',
                              'path_params': {'param1': 'C'},
                              'body': pet_instance,
                              },
                             {'method': 'PUT',
                              'resource_path': '/service/v1/{param1}/foo',
                              'path_params': {'param1': 'C'},
                              'body': pet_instance_dict,
                              },
                             {'method': 'PUT',
                              'resource_path': '/service/v1/{param1}/foo',
                              'path_params': {'param1': 'C'},
                              'body': pet_instance_json,
                              },
                            {
                                'method': 'POST',
                                'resource_path': '/service/v1/bar/foo',
                                'body': b'..some binary content..',
                            },
                          ])
async def test_serialize_and_call(snapshot, mocker, httpx_mock: HTTPXMock, waylay_api_client: ApiClient, test_input: dict[str, Any], request):
    """Test REST param serializer."""
    test_input = _retreive_fixture_values(request, test_input)
    serialized_params = waylay_api_client.param_serialize(**test_input)
    assert serialized_params == snapshot

    mocker.patch('waylay.auth.WaylayTokenAuth.assure_valid_token', lambda *args: WaylayTokenStub())
    httpx_mock.add_response()
    await waylay_api_client.call_api(**serialized_params)
    requests = httpx_mock.get_requests()
    assert (requests, [_headers_and_content_snap(r.headers, r.read()) for r in requests]) == snapshot


def _headers_and_content_snap(headers: dict[str, str], content: bytes):
    # mask `boundary` from multipart/form-data uploads
    content_type = headers.get('content-type')
    if content_type and content_type.startswith('multipart/form-data'):
        pattern = re.compile(r'(boundary=)([^\s;]+)')
        match = pattern.search(content_type)
        if match:
            boundary = match.group(2)
            headers.update({
                'content-type': content_type.replace(boundary, '<boundary>')
            })
            content = content.decode().replace(boundary, '<boundary>').encode()
        re.sub(pattern, r'\1***', content_type)
    return (headers, content)


async def test_serialize_and_call_does_not_support_body_and_files(waylay_api_client: ApiClient):
    """REST param serializer should not support setting both `body` and `files`"""
    serialized_params = waylay_api_client.param_serialize(
        method='POST',
        resource_path='/foo',
        body={
            'key': 'value'},
        files={
            'file1': b'<binary>'})
    with pytest.raises(ApiValueError):
        await waylay_api_client.call_api(**serialized_params)


@pytest.mark.parametrize("response_kwargs,response_type_map", [
    # primtive response types
    (
        {'status_code': 200, 'text': 'some_text_resopnse', 'headers': {'x-resp-header': 'resp_header_value'}},
        {'200': str}
    ),
    (
        {'status_code': 200, 'text': 'some_text_resopnse'},
        {'200': 'str'}
    ),
    (
        {'status_code': 200, 'text': 'some_text_resopnse'},
        {}  # no response mapping
    ),
    (
        {'status_code': 200, 'text': '123'},
        {'200': int}
    ),
    (
        {'status_code': 200, 'text': '123.456'},
        {'200': float}
    ),
    (
        {'status_code': 200, 'json': 123.456},
        {'200': 'float'}
    ),
    (
        {'status_code': 200, 'json': '123'},
        {}  # no response mapping
    ),
    (
        {'status_code': 200, 'json': 123},
        {}  # no response mapping
    ),
    (
        {'status_code': 200, 'text': 'true'},
        {'200': bool}
    ),
    (
        {'status_code': 200, 'json': False},
        {'200': 'bool'}  # TODO fix parsing of falsy boolean values (currently returns 'bytes')
    ),
    (
        {'status_code': 200, 'json': True},
        {}  # no response mapping
    ),
    (
        {'status_code': 200, 'json': {'hello': 'world', 'key': [1, 2, 3]}},
        {'200': object}
    ),
    (
        {'status_code': 200, 'json': {'hello': 'world', 'key': [1, 2, 3]}},
        {}  # no response mapping
    ),
    (
        {'status_code': 200, 'content': None},
        {}  # no response mapping
    ),
    (
        {'status_code': 200, 'content': None},
        {'200': None}
    ),
    # dict response type
    (
        {'status_code': 201, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'201': Dict[str, str]}
    ),
    (
        {'status_code': 201, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'2XX': Dict[str, str]}
    ),
    (
        {'status_code': 201, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'*': 'Dict[str, str]'}
    ),
    (
        {'status_code': 201, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'default': dict}
    ),
    (
        {'status_code': 201, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'4XX': Dict[str, str]}  # no response mapping
    ),
    # binary response types
    (
        {'status_code': 202, 'content': b'some binary file content,', 'headers': {
            'Content-Disposition': 'file_name.ext', 'content-type': 'application/octet-stream'}},
        {'202': bytearray}
    ),
    (
        {'status_code': 202, 'content': b'some binary file content,', 'headers': {
            'Content-Disposition': 'file_name.ext', 'content-type': 'application/octet-stream'}},
        {'2XX': 'bytearray'}
    ),
    (
        {'status_code': 202, 'content': b'some binary file content,', 'headers': {
            'Content-Disposition': 'file_name.ext', 'content-type': 'application/octet-stream'}},
        {'*': bytes}
    ),
    # list response types
    (
        {'status_code': 200, 'json': ['11', '22', 33]},
        {'2XX': List[int]}  # TODO fix parsing subtype (currently array elements aren't converted to int)
    ),
    (
        {'status_code': 200, 'json': ['11', '22', 33]},
        {'2XX': 'List[int]'}
    ),
    (
        {'status_code': 200, 'json': ['hello', 'world', 123, {'key': 'value'}]},
        {'2XX': List[Union[str, int, Dict[str, Any]]]}
    ),
    (
        {'status_code': 200, 'json': ['hello', 'world', 123, {'key': 'value'}]},
        {'2XX': list}
    ),
    (
        {'status_code': 200, 'json': ['hello', 'world', 123, {'key': 'value'}]},
        {}  # no response type
    ),
    # datetime response types
    (
        {'status_code': 200, 'text': str(datetime(2023, 12, 25, minute=1).isoformat())},
        {'200': datetime}
    ),
    (
        {'status_code': 200, 'text': str(datetime(2023, 12, 25, minute=1).isoformat())},
        {'2XX': date}
    ),
    (
        {'status_code': 200, 'text': str(datetime(2023, 12, 25, minute=1).isoformat())},
        {'2XX': str}
    ),
    (
        {'status_code': 200, 'text': str(datetime(2023, 12, 25, minute=1).isoformat())},
        {}  # no response type
    ),
    # custom model response types
    (
        {'status_code': 200, 'json': pet_instance_dict},
        {'200': Pet}
    ),
    (
        {'status_code': 200, 'text': pet_instance_json},
        {'2XX': Pet}
    ),
    (
        {'status_code': 200, 'content': pet_instance_json},
        {'*': Pet}
    ),
    (
        {'status_code': 200, 'json': pet_instance_dict},
        {'200': Any}
    ),
    (
        {'status_code': 200, 'json': pet_instance_dict},
        {'200': None}
    ),
    (
        {'status_code': 200, 'json': pet_instance_dict},
        {}
    ),
    (
        {'status_code': 200, 'json': pet_instance_dict},
        {'200': 'unit.api.example.pet_model.Pet'}
    ),
])
def test_deserialize(snapshot, waylay_api_client: ApiClient,
                     response_kwargs: Dict[str, Any], response_type_map: Any, request):
    """Test REST param deserializer."""
    response_kwargs = _retreive_fixture_values(request, response_kwargs)
    deserialized = waylay_api_client.response_deserialize(RESTResponse(**response_kwargs), response_type_map)
    assert (
        deserialized,
        type(deserialized.data).__name__,
        deserialized.data,
    ) == snapshot(name=f"{deserialized.status_code}:{deserialized.raw_data}@{str(response_type_map)}")


@pytest.mark.parametrize("response_kwargs,response_type_map", [
    (
        {'status_code': 404, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'404': Dict[str, str]}
    ),
    (
        {'status_code': 404, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'4XX': dict}
    ),
    (
        {'status_code': 404, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {'4XX': Any}
    ),
    (
        {'status_code': 404, 'text': "some not found message"},
        {'4XX': Any}
    ),
    (
        {'status_code': 404, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"}},
        {}  # no response mapping
    ),
    (
        {'status_code': 400, 'json': pet_instance_dict},
        {'400': Pet}
    ),
    (
        {'status_code': 400, 'content': pet_instance_json},
        {'default': Any}
    ),
    (
        {'status_code': 400, 'json': pet_instance_dict},
        {}
    ),
])
def test_deserialize_error_responses(snapshot, waylay_api_client: ApiClient,
                                     response_kwargs: Dict[str, Any], response_type_map: Any, request):
    """Test REST param deserializer when error response."""
    response_kwargs = _retreive_fixture_values(request, response_kwargs)
    with pytest.raises(ApiError) as excinfo:
        waylay_api_client.response_deserialize(RESTResponse(**response_kwargs), response_type_map)
    assert (str(excinfo.value), type(excinfo.value.data).__name__,
            excinfo.value.data) == snapshot(name=str(response_type_map))


def _retreive_fixture_values(request, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    for arg_key, arg_value in kwargs.items():
        if (callable(arg_value)):
            _arg_value = request.getfixturevalue(arg_value.__name__)
            kwargs.update({arg_key: _arg_value})
    return kwargs


async def test_default_headers(waylay_api_client: ApiClient):
    """Test setting and getting of default user agent."""
    _user_agent = 'test'
    waylay_api_client.user_agent = _user_agent
    assert waylay_api_client.user_agent == _user_agent
    assert waylay_api_client.default_headers['User-Agent'] == _user_agent

    [name, value] = ['x-header-name', 'header_value']
    waylay_api_client.set_default_header(name, value)
    assert waylay_api_client.default_headers[name] == value

@pytest.mark.parametrize("request_kwargs", [
    { 'method': 'GET', 'url': 'https://example.com/foo/', '_request_timeout' : 10.0},
    { 'method': 'GET', 'url': 'https://example.com/foo/', '_request_timeout' : 10},
    { 'method': 'GET', 'url': 'https://example.com/foo/', '_request_timeout' : (10, 5, 5, 5)}  # (connect, read, write, pool)
])
async def test_request_timeout(waylay_api_client: ApiClient, httpx_mock: HTTPXMock, mocker: MockerFixture, request_kwargs):
    """Test request timeout."""
    spy = mocker.spy(waylay_api_client.rest_client.client, 'request')
    mocker.patch('waylay.auth.WaylayTokenAuth.assure_valid_token', lambda *args: WaylayTokenStub())
    httpx_mock.add_response()
    await waylay_api_client.call_api(**request_kwargs)
    _httpx_args = {'params': None, 'headers': {}}
    _httpx_args.update(request_kwargs)
    _httpx_args['timeout'] = _httpx_args.pop('_request_timeout')
    spy.assert_called_once_with(**_httpx_args)