"""Test suite for package `waylay.api`."""

from typing import Any, Dict, List, Union
from unittest import mock
from unittest.mock import patch
import pytest
from datetime import datetime, date

from waylay.auth import TokenCredentials
from waylay.config import WaylayConfig
from waylay.api import ApiConfig, ApiClient
from waylay.api.rest import RESTResponse

from .example.pet_model import Pet
from .example.pet_fixtures import pet_instance, pet_instance_dict, pet_instance_json


@pytest.fixture
def waylay_token_credentials() -> TokenCredentials:
    return TokenCredentials(token='dummy_token',gateway_url='https://api-example.io')

@pytest.fixture
def waylay_config(waylay_token_credentials: TokenCredentials) -> WaylayConfig:
    return WaylayConfig(credentials=waylay_token_credentials)

@pytest.fixture
def waylay_api_config(waylay_config: WaylayConfig) -> ApiConfig:
    return ApiConfig(waylay_config)

@pytest.fixture
def waylay_api_client(waylay_api_config: ApiConfig) -> ApiClient:
    return ApiClient(waylay_api_config)


@pytest.mark.parametrize("test_input", [
    {
        'method': 'GET',
        'resource_path': '/service/v1/{param1}/foo/{param2}',
        'path_params': {'param1': 'A', 'param2': 'B'},
        'query_params': {'key1': 'value1', 'key2': 'value2'},
        'header_params': {'x-my-header': 'header_value'},
        'body': None,
        'files': None,
    },
    {
        'method': 'PATCH',
        'resource_path': '/service/v1/{param1}/bar/{missing_param}',
        'path_params': {'param1': 'A', 'param_not_in_resource_path': 'B'},
        'query_params': None,
        'header_params': {'x-my-header': 'header_value'},
        'body': {'array_key': ['val1', 'val2'], 'tuple_key': ('val3', 123, {'key': 'value'}, None), 'timestamp': datetime(1999, 9, 28, hour=12, minute=30, second=59)},
    },
    {
        'method': 'POST',
        'resource_path': '/service/v1/cruz/',
        'path_params': None,
        'query_params': {'key1': 15},
        'files': {'file1': b'<... binary content ...>', 'file2': '<... other binary content ...>'},
    },
    {
        'method': 'PUT',
        'resource_path': '/service/v1/{param1}/foo',
        'path_params': {'param1': 'C'},
        'body': pet_instance,
    },
    {
        'method': 'PUT',
        'resource_path': '/service/v1/{param1}/foo',
        'path_params': {'param1': 'C'},
        'body': pet_instance_dict,
    },
    {
        'method': 'PUT',
        'resource_path': '/service/v1/{param1}/foo',
        'path_params': {'param1': 'C'},
        'body': pet_instance_json,
    },
])
def test_param_serialize(snapshot, waylay_api_client: ApiClient, test_input: dict[str, Any], request):
    """Test REST param serializer"""
    test_input = _retreive_fixture_values(request, test_input)
    assert waylay_api_client.param_serialize(**test_input) == snapshot

@pytest.mark.parametrize("response_kwargs,response_type", [
    (
        { 'status_code': 200, 'text' : 'some_text_resopnse', 'headers' : {'x-resp-header': 'resp_header_value'} },
        str 
    ),
    (
        { 'status_code': 404, 'json': {"message": "some not found message", "code": "RESOURCE_NOT_FOUND"} },
        Dict[str, str]
    ),
    (
        { 'status_code': 202, 'content': b'some binary file content,', 'headers':{'Content-Disposition': 'file_name.ext', 'content-type': 'application/octet-stream'} },
        bytearray
    ),
    (
        { 'status_code': 200, 'json': ['hello', 'world', 123, {'key': 'value'}]},
        List[Union[str, int, Dict[str, Any]]]
    ),
    (
        { 'status_code': 200, 'text': str(datetime(2023, 12, 25, minute=1).isoformat())},
        datetime
    ),
    (
        { 'status_code': 200, 'text': str(datetime(2023, 12, 25, minute=1).isoformat())},
        date
    ),
    (
        { 'status_code': 200, 'text': str(datetime(2023, 12, 25, minute=1).isoformat())},
        str
    ),
    (
        { 'status_code':200, 'json': pet_instance_dict },
        Pet
    ),
    (
        { 'status_code':200, 'text': pet_instance_json },
        Pet
    ),
    (
        { 'status_code':200, 'content': pet_instance_json },
        Pet
    ),
])
def test_deserialize(snapshot, waylay_api_client: ApiClient, response_kwargs: Dict[str, Any], response_type: Any, request):
    """Test REST param serializer"""
    response_kwargs = _retreive_fixture_values(request, response_kwargs)
    deserialized = waylay_api_client.deserialize(RESTResponse(**response_kwargs), response_type)
    assert (type(deserialized).__name__, deserialized) == snapshot


def _retreive_fixture_values(request, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    for arg_key, arg_value in kwargs.items():
        if (callable(arg_value)):
            _arg_value = request.getfixturevalue(arg_value.__name__)
            kwargs.update({arg_key: _arg_value})
    return kwargs
