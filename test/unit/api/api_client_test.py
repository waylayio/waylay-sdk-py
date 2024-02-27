"""Test suite for package `waylay.api`."""

import re
from typing import Any, Dict, List, Union
from datetime import datetime, date

import pytest
from pytest_httpx import HTTPXMock
from pytest_mock import MockerFixture

from waylay.sdk.auth import TokenCredentials
from waylay.sdk.config import WaylayConfig
from waylay.sdk.api import ApiClient

from waylay.sdk.api.http import Response as RESTResponse
from waylay.sdk.api.exceptions import ApiError, ApiValueError

from ..fixtures import WaylayTokenStub
from .example.pet_model import Pet, PetType
from .example.pet_fixtures import pet_instance, pet_instance_dict, pet_instance_json


@pytest.fixture(name="waylay_credentials")
def _fixture_waylay_token_credentials() -> TokenCredentials:
    return TokenCredentials(token="dummy_token", gateway_url="https://api-example.io")


@pytest.fixture(name="waylay_config")
def _fixture_waylay_config(waylay_credentials) -> WaylayConfig:
    return WaylayConfig(waylay_credentials)


@pytest.fixture(name="waylay_api_client")
def _fixture_waylay_api_client(waylay_config: WaylayConfig) -> ApiClient:
    return ApiClient(waylay_config, { 'auth': None })


SERIALIZE_CASES = {
    "params_and_query": {
        "method": "GET",
        "resource_path": "/service/v1/{param1}/foo/{param2}",
        "path_params": {"param1": "A", "param2": "B"},
        "query_params": {"key1": "value1", "key2": "value2"},
        "header_params": {"x-my-header": "header_value"},
        "body": None,
        "files": None,
    },
    "params_and_body": {
        "method": "PATCH",
        "resource_path": "/service/v1/{param1}/bar/{missing_param}",
        "path_params": {"param1": "A", "param_not_in_resource_path": "B"},
        "query_params": None,
        "header_params": {"x-my-header": "header_value"},
        "body": {
            "array_key": ["val1", "val2"],
            "tuple_key": ("val3", 123, {"key": "value"}, None),
            "timestamp": datetime(1999, 9, 28, hour=12, minute=30, second=59),
        },
    },
    "files": {
        "method": "POST",
        "resource_path": "/service/v1/cruz/",
        "path_params": None,
        "query_params": {"key1": 15},
        "files": {
            "file1": b"<... binary content ...>",
            "file2": "<... other binary content ...>",
        },
    },
    "pet_body": {
        "method": "PUT",
        "resource_path": "/service/v1/{param1}/foo",
        "path_params": {"param1": "C"},
        "body": pet_instance,
    },
    "pet_dict_body": {
        "method": "PUT",
        "resource_path": "/service/v1/{param1}/foo",
        "path_params": {"param1": "C"},
        "body": pet_instance_dict,
    },
    "pet_json_body": {
        "method": "PUT",
        "resource_path": "/service/v1/{param1}/foo",
        "path_params": {"param1": "C"},
        "body": pet_instance_json,
    },
    "binary_body": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "body": b"..some binary content..",
    },
    "form": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "header_params": {"Content-Type": "application/x-www-form-urlencoded"},
        "body": {"key": "value"},
    },
    "body_and_files" : {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "header_params": {"Content-Type": "application/x-www-form-urlencoded"},
        "body": {"key": "value"},
        "files" : {
            "file1": b"<binary>"
        }
    }
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
):
    """Test REST param serializer."""
    test_input = _retrieve_fixture_values(request, test_input)
    serialized_params = waylay_api_client.param_serialize(**test_input)
    assert serialized_params == snapshot
    httpx_mock.add_response()
    await waylay_api_client.call_api(**serialized_params)
    requests = httpx_mock.get_requests()
    assert (
        requests,
        [_headers_and_content_snap(r.headers, r.read()) for r in requests],
    ) == snapshot


def _headers_and_content_snap(headers: dict[str, str], content: bytes):
    # mask `boundary` from multipart/form-data uploads
    content_type = headers.get("content-type")
    if not content_type:
        return (headers, content)
    if content_type.startswith("multipart/form-data"):
        pattern = re.compile(r"(boundary=)([^\s;]+)")
        match = pattern.search(content_type)
        if not match:
            return (headers, content)
        boundary = match.group(2)
        headers.update(
            {"content-type": content_type.replace(boundary, "<boundary>")}
        )
        content = content.decode().replace(boundary, "<boundary>").encode()
    if content_type.startswith("application/x-www-form-urlencoded"):
        decoded_content = content.decode().split('\r\n')
        boundary = decoded_content[0]
        content = '\r\n'.join(
            c.replace(boundary, '--- boundary ---') for c in decoded_content
        )
    return (headers, content)


async def test_call_invalid_method(waylay_api_client: ApiClient):
    """REST client should throw on invalid http method."""
    with pytest.raises(ApiValueError):
        await waylay_api_client.call_api(method="invalid", url="https://dummy.io")


@pytest.mark.parametrize(
    "response_kwargs,response_type_map",
    [
        # primitive response types
        (
            {
                "status_code": 200,
                "text": "some_text_resopnse",
                "headers": {"x-resp-header": "resp_header_value"},
            },
            {"200": str},
        ),
        ({"status_code": 200, "text": "some_text_resopnse"}, {"200": "str"}),
        (
            {"status_code": 200, "text": "some_text_resopnse"},
            {},  # no response mapping
        ),
        ({"status_code": 200, "text": "123"}, {"200": int}),
        ({"status_code": 200, "text": "123.456"}, {"200": float}),
        ({"status_code": 200, "json": 123.456}, {"200": "float"}),
        (
            {"status_code": 200, "json": "123"},
            {},  # no response mapping
        ),
        (
            {"status_code": 200, "json": 123},
            {},  # no response mapping
        ),
        ({"status_code": 200, "text": "true"}, {"200": bool}),
        (
            {"status_code": 200, "json": False},
            {
                "200": "bool"
            },  # TODO fix parsing of falsy boolean values (currently returns 'bytes')
        ),
        (
            {"status_code": 200, "json": True},
            {},  # no response mapping
        ),
        (
            {"status_code": 200, "json": {"hello": "world", "key": [1, 2, 3]}},
            {"200": object},
        ),
        (
            {"status_code": 200, "json": {"hello": "world", "key": [1, 2, 3]}},
            {},  # no response mapping
        ),
        (
            {"status_code": 200, "content": None},
            {},  # no response mapping
        ),
        ({"status_code": 200, "content": None}, {"200": None}),
        # dict response type
        (
            {
                "status_code": 201,
                "json": {
                    "message": "some not found message",
                    "code": "RESOURCE_NOT_FOUND",
                },
            },
            {"201": Dict[str, str]},
        ),
        (
            {
                "status_code": 201,
                "json": {
                    "message": "some not found message",
                    "code": "RESOURCE_NOT_FOUND",
                },
            },
            {"2XX": Dict[str, str]},
        ),
        (
            {
                "status_code": 201,
                "json": {
                    "message": "some not found message",
                    "code": "RESOURCE_NOT_FOUND",
                },
            },
            {"*": "Dict[str, str]"},
        ),
        (
            {
                "status_code": 201,
                "json": {
                    "message": "some not found message",
                    "code": "RESOURCE_NOT_FOUND",
                },
            },
            {"default": dict},
        ),
        (
            {
                "status_code": 201,
                "json": {
                    "message": "some not found message",
                    "code": "RESOURCE_NOT_FOUND",
                },
            },
            {"4XX": Dict[str, str]},  # no response mapping
        ),
        # binary response types
        (
            {
                "status_code": 202,
                "content": b"some binary file content,",
                "headers": {"content-type": "application/octet-stream"},
            },
            {"202": bytearray},
        ),
        (
            {
                "status_code": 202,
                "content": b"some binary file content,",
                "headers": {"content-type": "application/octet-stream"},
            },
            {"2XX": "bytearray"},
        ),
        (
            {
                "status_code": 202,
                "content": b"some binary file content,",
                "headers": {"content-type": "application/octet-stream"},
            },
            {"*": bytes},
        ),
        # list response types
        (
            {"status_code": 200, "json": ["11", "22", 33]},
            {
                "2XX": List[int]
            },  # TODO fix parsing subtype (currently array elements aren't converted to int)
        ),
        ({"status_code": 200, "json": ["11", "22", 33]}, {"2XX": "List[int]"}),
        (
            {"status_code": 200, "json": ["hello", "world", 123, {"key": "value"}]},
            {"2XX": List[Union[str, int, Dict[str, Any]]]},
        ),
        (
            {"status_code": 200, "json": ["hello", "world", 123, {"key": "value"}]},
            {"2XX": list},
        ),
        (
            {"status_code": 200, "json": ["hello", "world", 123, {"key": "value"}]},
            {},  # no response type
        ),
        # datetime response types
        (
            {
                "status_code": 200,
                "text": str(datetime(2023, 12, 25, minute=1).isoformat()),
            },
            {"200": datetime},
        ),
        (
            {
                "status_code": 200,
                "text": str(datetime(2023, 12, 25, minute=1).isoformat()),
            },
            {"2XX": date},
        ),
        (
            {
                "status_code": 200,
                "text": str("2023/12/25:12.02.20"),
            },  # invalid date should result in str
            {"2XX": date},
        ),
        (
            {
                "status_code": 200,
                "text": str(datetime(2023, 12, 25, minute=1).isoformat()),
            },
            {"2XX": str},
        ),
        (
            {
                "status_code": 200,
                "text": str(datetime(2023, 12, 25, minute=1).isoformat()),
            },
            {},  # no response type
        ),
        # enum response types
        ({"status_code": 200, "text": "dog"}, {"*": PetType}),
        # custom model response types
        ({"status_code": 200, "json": pet_instance_dict}, {"200": Pet}),
        ({"status_code": 200, "text": pet_instance_json}, {"2XX": Pet}),
        ({"status_code": 200, "content": pet_instance_json}, {"*": Pet}),
        ({"status_code": 200, "json": pet_instance_dict}, {"200": Any}),
        ({"status_code": 200, "json": pet_instance_dict}, {"200": None}),
        ({"status_code": 200, "json": pet_instance_dict}, {}),
        (
            {"status_code": 200, "json": pet_instance_dict},
            {"200": "unit.api.example.pet_model.Pet"},
        ),
        (
            {"status_code": 200, "json": pet_instance_dict},
            {"200": "unit.api.example.pet_model.Unexisting"},
        ),
        (
            {"status_code": 200, "json": pet_instance_dict},
            {"200": "some.unexisting.module.Pet"},
        ),
    ],
)
def test_deserialize(
    snapshot,
    waylay_api_client: ApiClient,
    response_kwargs: Dict[str, Any],
    response_type_map: Any,
    request,
):
    """Test REST param deserializer."""
    response_kwargs = _retrieve_fixture_values(request, response_kwargs)
    deserialized = waylay_api_client.response_deserialize(
        RESTResponse(**response_kwargs), response_type_map
    )
    assert (
        deserialized,
        type(deserialized.data).__name__,
        deserialized.data,
    ) == snapshot(
        name=f"{deserialized.status_code}:{deserialized.raw_data}@{str(response_type_map)}"
    )


@pytest.mark.parametrize(
    "response_kwargs,response_type_map",
    [
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
    ],
)
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
        if callable(arg_value):
            _arg_value = request.getfixturevalue(arg_value.__name__)
            kwargs.update({arg_key: _arg_value})
    return kwargs


@pytest.mark.parametrize(
    "method, url, timeout",
    [
        ["GET", "https://example.com/foo/", 10.0],
        ["GET", "https://example.com/foo/", 10],
        [
            "GET",
            "https://example.com/foo/",
            (10, 5, 5, 5),
        ],  # (connect, read, write, pool)
        ["GET", "https://example.com/foo/", None],  # default
    ],
)
async def test_request_timeout(
    method,
    url,
    timeout,
    waylay_api_client: ApiClient,
    httpx_mock: HTTPXMock,
    mocker: MockerFixture,
):
    """Test request timeout."""
    spy = mocker.spy(waylay_api_client.http_client, "request")
    mocker.patch(
        "waylay.sdk.auth.provider.WaylayTokenAuth.assure_valid_token",
        lambda *args: WaylayTokenStub(),
    )
    httpx_mock.add_response()
    await waylay_api_client.call_api(method, url, _request_timeout=timeout)
    expected_timeout = timeout
    if expected_timeout:
        spy.assert_called_once_with(method, url, timeout=expected_timeout)
    else:
        spy.assert_called_once_with(method, url)
