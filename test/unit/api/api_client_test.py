"""Test suite for package `waylay.api`."""

from typing import Any, Dict, List, Union
from datetime import datetime, date

import pytest
from pytest_httpx import HTTPXMock

from waylay.sdk.auth import TokenCredentials
from waylay.sdk.config import WaylayConfig
from waylay.sdk.api import ApiClient
from waylay.sdk.api._models import Model

from waylay.sdk.api.http import Response as RESTResponse
from waylay.sdk.api.exceptions import ApiError, ApiValueError

from .example.pet_model import Pet, PetType, PetList
from .example.pet_fixtures import (
    pet_instance,
    pet_instance_dict,
    pet_instance_json,
    pet_list_instance_dict,
)


@pytest.fixture(name="waylay_credentials")
def _fixture_waylay_token_credentials() -> TokenCredentials:
    return TokenCredentials(token="dummy_token", gateway_url="https://api-example.io")


@pytest.fixture(name="waylay_config")
def _fixture_waylay_config(waylay_credentials) -> WaylayConfig:
    return WaylayConfig(waylay_credentials)


@pytest.fixture(name="waylay_api_client")
def _fixture_waylay_api_client(waylay_config: WaylayConfig) -> ApiClient:
    return ApiClient(waylay_config, {"auth": None})


SERIALIZE_CASES = {
    "path_and_query_params": {
        "method": "GET",
        "resource_path": "/service/v1/{param1}/foo/{param2}",
        "path_params": {"param1": "A", "param2": "B"},
        "params": {"key1": "value1", "key2": "value2"},
        "headers": {"x-my-header": "header_value"},
    },
    "params_and_body": {
        "method": "PATCH",
        "resource_path": "/service/v1/{param1}/bar/{missing_param}",
        "path_params": {"param1": "A", "param_not_in_resource_path": "B"},
        "headers": {"x-my-header": "header_value"},
        "json": {
            "array_key": ["val1", "val2"],
            "tuple_key": ("val3", 123, {"key": "value"}, None),
            "timestamp": datetime(1999, 9, 28, hour=12, minute=30, second=59),
        },
    },
    "files": {
        "method": "POST",
        "resource_path": "/service/v1/cruz/",
        "params": {"key1": 15},
        "files": {
            "file1": b"<... binary content ...>",
            "file2": "<... other binary content ...>",
        },
    },
    "pet_body": {
        "method": "PUT",
        "resource_path": "/service/v1/{param1}/foo",
        "path_params": {"param1": "C"},
        "json": pet_instance,
    },
    "pet_dict_body": {
        "method": "PUT",
        "resource_path": "/service/v1/{param1}/foo",
        "path_params": {"param1": "C"},
        "json": pet_instance_dict,
    },
    "pet_json_body": {
        "method": "PUT",
        "resource_path": "/service/v1/{param1}/foo",
        "path_params": {"param1": "C"},
        "json": pet_instance_json,
    },
    "binary_body": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "content": b"..some binary content..",
    },
    "form": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "data": {"key": "value"},
    },
    "data_and_files": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "data": {"key": "value"},
        "files": {"file1": b"<binary>"},
    },
}


@pytest.mark.parametrize(
    "test_input", SERIALIZE_CASES.values(), ids=SERIALIZE_CASES.keys()
)
async def test_serialize_and_call(
    snapshot,
    httpx_mock: HTTPXMock,
    waylay_api_client: ApiClient,
    test_input: dict[str, Any],
    request,
    mocker,
):
    """Test REST param serializer."""
    test_input = _retrieve_fixture_values(request, test_input)
    mocker.patch(
        "httpx._models.get_multipart_boundary_from_content_type",
        lambda content_type: b"---boundary---",
    )
    request = waylay_api_client.build_request(**test_input)
    assert request.__dict__ == snapshot
    httpx_mock.add_response()
    await waylay_api_client.send(request)
    requests = httpx_mock.get_requests()
    assert (
        requests,
        [(r.headers, r.read()) for r in requests],
    ) == snapshot


async def test_call_invalid_method(waylay_api_client: ApiClient):
    """REST client should throw on invalid http method."""
    with pytest.raises(ApiValueError):
        waylay_api_client.build_request(method="invalid", resource_path="/")


DESERIALIZE_CASES = [
    (
        "text_str_str",
        {
            "status_code": 200,
            "text": "some_text_resopnse",
            "headers": {"x-resp-header": "resp_header_value"},
        },
        {"200": str},
        None,
    ),
    (
        "text_str_str_str",
        {"status_code": 200, "text": "some_text_resopnse"},
        {"200": "str"},
        None,
    ),
    (
        "text_str",
        {"status_code": 200, "text": "some_text_resopnse"},
        {},  # no response mapping
        None,
    ),
    ("primitive_text_int", {"status_code": 200, "text": "123"}, {"200": int}, None),
    (
        "primitive_text_float",
        {"status_code": 200, "text": "123.456"},
        {"200": float},
        None,
    ),
    (
        "primitive_json_float",
        {"status_code": 200, "json": 123.456},
        {"200": "float"},
        None,
    ),
    (
        "json_str",
        {"status_code": 200, "json": "123"},
        {},  # no response mapping
        None,
    ),
    (
        "json_number",
        {"status_code": 200, "json": 123},
        {},  # no response mapping
        None,
    ),
    ("json_str_bool", {"status_code": 200, "text": "true"}, {"200": bool}, None),
    (
        "json_bool_bool",
        {"status_code": 200, "json": False},
        {
            "200": "bool"
        },  # TODO fix parsing of falsy boolean values (currently returns 'bytes')
        None,
    ),
    (
        "json_bool",
        {"status_code": 200, "json": True},
        {},  # no response mapping
        None,
    ),
    (
        "json_dict_object",
        {"status_code": 200, "json": {"hello": "world", "key": [1, 2, 3]}},
        {"200": object},
        None,
    ),
    (
        "json_dict",
        {"status_code": 200, "json": {"hello": "world", "key": [1, 2, 3]}},
        {},  # no response mapping
        None,
    ),
    (
        "content_none",
        {"status_code": 200, "content": None},
        {},  # no response mapping
        None,
    ),
    ("content_none_none", {"status_code": 200, "content": None}, {"200": None}, None),
    # dict response type
    (
        "json_dict_dict",
        {
            "status_code": 201,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"201": Dict[str, str]},
        None,
    ),
    (
        "json_dict_2XX_dict",
        {
            "status_code": 201,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"2XX": Dict[str, str]},
        None,
    ),
    (
        "json_dict_*_dict",
        {
            "status_code": 201,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"*": "Dict[str, str]"},
        None,
    ),
    (
        "json_dict_default_dict",
        {
            "status_code": 201,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"default": dict},
        None,
    ),
    (
        "json_dict_no_mapping",
        {
            "status_code": 201,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"4XX": Dict[str, str]},  # no response mapping
        None,
    ),
    # binary response types
    (
        "content_bin_bytearray",
        {
            "status_code": 202,
            "content": b"some binary file content,",
            "headers": {"content-type": "application/octet-stream"},
        },
        {"202": bytearray},
        None,
    ),
    (
        "content_bin_XX_bytearay",
        {
            "status_code": 202,
            "content": b"some binary file content,",
            "headers": {"content-type": "application/octet-stream"},
        },
        {"2XX": "bytearray"},
        None,
    ),
    (
        "content_bin_*_bytearray",
        {
            "status_code": 202,
            "content": b"some binary file content,",
            "headers": {"content-type": "application/octet-stream"},
        },
        {"*": bytes},
        None,
    ),
    # list response types
    (
        "json_list_XX_list_int",
        {"status_code": 200, "json": ["11", "22", 33]},
        {"2XX": List[int]},
        None,
    ),
    (
        "json_list_X_list_int_str",
        {"status_code": 200, "json": ["11", "22", 33]},
        {"2XX": "List[int]"},
        None,
    ),
    (
        "json_list_X_union",
        {"status_code": 200, "json": ["hello", "world", 123, {"key": "value"}]},
        {"2XX": List[Union[str, int, Dict[str, Any]]]},
        None,
    ),
    (
        "json_list_x_list",
        {"status_code": 200, "json": ["hello", "world", 123, {"key": "value"}]},
        {"2XX": list},
        None,
    ),
    (
        "json_list",
        {"status_code": 200, "json": ["hello", "world", 123, {"key": "value"}]},
        {},  # no response type
        None,
    ),
    # datetime response types
    (
        "text_str_datetime",
        {
            "status_code": 200,
            "text": datetime(2023, 12, 25, minute=1).isoformat(),
        },
        {"200": datetime},
        None,
    ),
    (
        "text_str_date",
        {
            "status_code": 200,
            "text": date(2023, 12, 25).isoformat(),
        },
        {"2XX": date},
        None,
    ),
    (
        "text_str_invalid_date",
        {
            "status_code": 200,
            "text": str("2023/12/25:12.02.20"),
        },  # invalid date should result in str
        {"2XX": date},
        None,
    ),
    (
        "text_datestr_str",
        {
            "status_code": 200,
            "text": datetime(2023, 12, 25, minute=1).isoformat(),
        },
        {"2XX": str},
        None,
    ),
    (
        "text_str",
        {
            "status_code": 200,
            "text": datetime(2023, 12, 25, minute=1).isoformat(),
        },
        {},  # no response type
        None,
    ),
    # enum response types
    ("text_str_Enum", {"status_code": 200, "text": "dog"}, {"*": PetType}, None),
    # fallback model responses
    (
        "json_dict_any_model",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": Model},
        None,
    ),
    (
        "json_list_any_model",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"*": Model},
        None,
    ),
    (
        "dict_with_self_model",
        {"status_code": 200, "json": {"self": "me"}},
        {"*": Model},
        None,
    ),
    # custom model response types
    (
        "json_dict_model",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": Pet},
        None,
    ),
    (
        "text_str_model",
        {"status_code": 200, "text": pet_instance_json},
        {"2XX": Pet},
        None,
    ),
    (
        "content_str_model",
        {"status_code": 200, "content": pet_instance_json},
        {"*": Pet},
        None,
    ),
    (
        "json_dict_any",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": Any},
        None,
    ),
    (
        "json_dict_none",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": None},
        None,
    ),
    ("json_dict", {"status_code": 200, "json": pet_instance_dict}, {}, None),
    (
        "json_list_model",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"200": PetList},
        None,
    ),
    (
        "json_dict_modelstr",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": "unit.api.example.pet_model.Pet"},
        None,
    ),
    (
        "json_dict_wrongmodelstr",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": "unit.api.example.pet_model.Unexisting"},
        None,
    ),
    (
        "json_dict_wrongmodulestr",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": "some.unexisting.module.Pet"},
        None,
    ),
    (
        "json_dict_union",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": Union[str, list[Pet], Pet]},
        None,
    ),
    (
        "json_dict_*_union",
        {"status_code": 200, "json": pet_instance_dict},
        {"*": Union[Pet]},
        None,
    ),
    (
        "json_dict_*_union_str",
        {"status_code": 200, "json": pet_instance_dict},
        {"*": "unit.api.example.pet_model.PetUnion"},
        None,
    ),
    (
        "json_list_*_union",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"*": "unit.api.example.pet_model.PetUnion"},
        None,
    ),
    # select path argument
    (
        "json_dict_str_path_name",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": str},
        "name",
    ),
    (
        "json_list_model_path_pets",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"200": List[Pet]},
        "pets",
    ),
    (
        "json_list_any_model_path_pets",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"200": List[Model]},
        "pets",
    ),
    (
        "json_list_list_path_[*].name",
        {"status_code": 200, "json": [pet_instance_dict]},
        {"200": "List[str]"},
        "[*].name",
    ),
    (
        "json_list_list_path_pets[*].name",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"200": "List[str]"},
        "pets[*].name",
    ),
]


@pytest.mark.parametrize(
    "response_kwargs,response_type_map,select_path",
    [c[1:] for c in DESERIALIZE_CASES],
    ids=[c[0] for c in DESERIALIZE_CASES],
)
def test_deserialize(
    snapshot,
    waylay_api_client: ApiClient,
    response_kwargs: Dict[str, Any],
    response_type_map: Any,
    select_path: str | None,
    request,
):
    """Test REST param deserializer."""
    response_kwargs = _retrieve_fixture_values(request, response_kwargs)
    response = RESTResponse(**response_kwargs)
    deserialized = waylay_api_client.response_deserialize(
        response, response_type_map, select_path
    )
    assert (
        response.content,
        response.status_code,
        response_type_map,
        select_path,
        type(deserialized).__name__,
        deserialized,
    ) == snapshot()


ERROR_RESP_CASES = [
    (
        {
            "status_code": 404,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"404": Dict[str, str]},
    ),
    (
        {
            "status_code": 404,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"4XX": dict},
    ),
    (
        {
            "status_code": 404,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"4XX": Any},
    ),
    ({"status_code": 404, "text": "some not found message"}, {"4XX": Any}),
    (
        {
            "status_code": 404,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {},  # no response mapping
    ),
    ({"status_code": 400, "json": pet_instance_dict}, {"400": Pet}),
    ({"status_code": 400, "content": pet_instance_json}, {"default": Any}),
    ({"status_code": 400, "json": pet_instance_dict}, {}),
]


@pytest.mark.parametrize("response_kwargs,response_type_map", ERROR_RESP_CASES)
def test_deserialize_error_responses(
    snapshot,
    waylay_api_client: ApiClient,
    response_kwargs: Dict[str, Any],
    response_type_map: Any,
    request,
):
    """Test REST param deserializer when error response."""
    response_kwargs = _retrieve_fixture_values(request, response_kwargs)
    with pytest.raises(ApiError) as excinfo:
        waylay_api_client.response_deserialize(
            RESTResponse(**response_kwargs), response_type_map
        )
    assert (
        str(excinfo.value),
        type(excinfo.value.data).__name__,
        excinfo.value.data,
    ) == snapshot(name=str(response_type_map))


def _retrieve_fixture_values(request, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    for arg_key, arg_value in kwargs.items():

        def _update_fixture_value(x):
            if callable(x):
                _arg_value = request.getfixturevalue(x.__name__)
                kwargs.update({arg_key: _arg_value})

        if isinstance(arg_value, list):
            for x in arg_value:
                _update_fixture_value(x)
        else:
            _update_fixture_value(arg_value)
    return kwargs


@pytest.mark.parametrize(
    "method, url, timeout, expected_timeout",
    [
        [
            "GET",
            "https://example.com/foo/",
            10.0,
            {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0},
        ],
        [
            "GET",
            "https://example.com/foo/",
            10,
            {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0},
        ],
        [
            "GET",
            "https://example.com/foo/",
            (10, 5, 5, 5),
            {"connect": 10, "read": 5, "write": 5, "pool": 5},
        ],  # (connect, read, write, pool)
        [
            "GET",
            "https://example.com/foo/",
            None,
            {"connect": 5.0, "read": 5.0, "write": 5.0, "pool": 5.0},
        ],
    ],
)
async def test_request_timeout(
    method,
    url,
    timeout,
    expected_timeout,
    waylay_api_client: ApiClient,
):
    """Test request timeout."""
    request = waylay_api_client.build_request(method, url, timeout=timeout)
    assert request.extensions.get("timeout", None) == expected_timeout
