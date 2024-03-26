"""Test suite for package `waylay.api`."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Union, AsyncIterator
from datetime import datetime, date
from pathlib import Path

import pytest
from syrupy.filters import paths
import httpx
from pytest_httpx import HTTPXMock

from waylay.sdk.auth import TokenCredentials
from waylay.sdk.config import WaylayConfig
from waylay.sdk.api import ApiClient
from waylay.sdk.api._models import Model

from waylay.sdk.api.http import Response, Request
from waylay.sdk.api.exceptions import ApiError, ApiValueError

from .example.pet_model import Pet, PetType, PetList, PetUnion
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


async def _iter_some_binary_content():
    yield b"iter"
    yield b"some"
    yield b"binary"
    yield b"content"


class BinaryReader:
    """Custom binary reader."""

    pos = 0
    data = b"some binary content"

    def read(self, b_len=2):
        """Read binary data."""
        pos = self.pos
        size = min(len(self.data) - pos, b_len)
        if size <= 0:
            return b""
        self.pos = pos + size
        return self.data[pos : pos + size]


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
    "binary_iterable": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "content": [b"some", b"binary", b"content"],
    },
    "binary_async_iterable": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "content": _iter_some_binary_content(),
    },
    "binary_io_buffer": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "content": (Path(__file__).parent / "__init__.py").open(mode="rb"),
    },
    "binary_io": {
        "method": "POST",
        "resource_path": "/service/v1/bar/foo",
        "content": BinaryReader(),
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
    httpx_mock.add_response()
    await waylay_api_client.send(request)
    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    request = requests[0]
    request_data = await request.aread()
    assert (
        request.__dict__,
        dict(request.headers),
        request_data,
    ) == snapshot(exclude=paths("0._content", "0.headers", "0.stream", "1.user-agent"))


async def test_call_invalid_method(waylay_api_client: ApiClient):
    """REST client should throw on invalid http method."""
    with pytest.raises(ApiValueError):
        waylay_api_client.build_request(method="invalid", resource_path="/")


async def test_call_invalid_content(waylay_api_client: ApiClient):
    """Cannot use a dict as `content` argument."""
    with pytest.raises(TypeError, match="Unexpected type"):
        waylay_api_client.build_request("POST", "", content={"should": "not work"})


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
        "json_dict_union",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": Union[str, list[Pet], Pet]},
        None,
    ),
    (
        "json_dict_*_dummy_union",
        {"status_code": 200, "json": pet_instance_dict},
        {"*": Union[Pet]},
        None,
    ),
    (
        "json_dict_*_union",
        {"status_code": 200, "json": pet_instance_dict},
        {"*": PetUnion},
        None,
    ),
    (
        "json_list_*_union",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"*": PetUnion},
        None,
    ),
    # Any response type (i.e. surpress deserialization)
    (
        "json_dict_model_any",
        {"status_code": 200, "json": pet_instance_dict},
        {"200": Any},
        None,
    ),
    # type constructors that are not recognized by pydantic
    (
        "json_dict_namespace",
        {
            "status_code": 201,
            "json": {
                "message": "some not found message",
                "code": "RESOURCE_NOT_FOUND",
            },
        },
        {"2XX": SimpleNamespace},  # TODO fix: should return SimpleNamespace
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
        {"200": List["str"]},
        "[*].name",
    ),
    (
        "json_list_list_path_pets[*].name",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"200": List[str]},
        "pets[*].name",
    ),
    (
        "json_list_list_path_pets[0].name",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"200": str},
        "pets[0].name",
    ),
    (
        "json_list_list_path_pets[1:].name",
        {"status_code": 200, "json": pet_list_instance_dict},
        {"200": List[str]},
        "pets[1:].name",
    ),
    # invalid/partial data
    (
        "json_model_invalid_field",
        {
            "status_code": 200,
            "json": {"name": 111, "owner": {"id": 456, "name": "Simon"}},
        },  # name type is int instead of str
        {"200": Pet},
        None,
    ),
    (
        "json_model_invalid_submodel_field",
        {
            "status_code": 200,
            "json": {"name": 111, "owner": {"id": "invalidId", "name": "Simon"}},
        },  # owner.id type is str instead of int
        {"200": Pet},
        None,
    ),
    (
        "json_model_missing_field",
        {
            "status_code": 200,
            "json": {"owner": {"id": 456, "name": "Simontis"}},
        },  # missing name
        {"200": Pet},
        None,
    ),
    (
        "json_model_missing_submodel_field",
        {"status_code": 200, "json": {"name": "Chop"}},  # missing owner
        {"200": Pet},
        None,
    ),
    (
        "json_model_invalid_submodel_list_field",
        {
            "status_code": 200,
            "json": {
                "pets": [
                    {"name": 111, "owner": {"id": "invalidId", "name": "Simon"}},
                    {"name": "Chop"},
                ]
            },
        },  # pets.0: id type is str instead of int, pets.1: missing owner
        {"200": PetList},
        None,
    ),
    (
        "json_model_invalid_submodule_list",
        {
            "status_code": 200,
            "json": [
                {"name": 111, "owner": {"id": "invalidId", "name": "Simon"}},
                {"name": "Chop"},
            ],
        },  # 0: id type is str instead of int, 1: missing owner
        {"200": List[Pet]},
        None,
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
    response = Response(**response_kwargs)
    deserialized = waylay_api_client.deserialize(
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


class TestResponseStream(httpx.AsyncByteStream):
    def __init__(self, chunks: List[bytes]):
        self.chunks_iter = iter(chunks)

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for b in self.chunks_iter:
            yield b

    async def aclose(self) -> None:
        self.chunks_iter = iter([])


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
    (
        {
            "status_code": 400,
            "headers": {"content-length": "3"},
            "request": Request(
                "GET",
                "http://all",
                params={"debug": "true"},
                headers={"x-feature": "flagged"},
            ),
            "stream": TestResponseStream([b"a", b"b", b"c"]),
        },
        {},
    ),
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
        waylay_api_client.deserialize(Response(**response_kwargs), response_type_map)
    assert (
        str(excinfo.value),
        type(excinfo.value.data).__name__,
        excinfo.value.data,
    ) == snapshot(name=str(response_type_map))


async def test_deserialize_partially_fetched_error_stream(
    waylay_api_client: ApiClient, snapshot
):
    resp = Response(
        status_code=400,
        stream=TestResponseStream([b"a", b"b", b"c"]),
        headers={"content-length": "3"},
    )
    await resp.aiter_raw(chunk_size=1).__anext__()
    with pytest.raises(ApiError) as excinfo:
        waylay_api_client.deserialize(resp, {})
    assert (
        str(excinfo.value),
        type(excinfo.value.data).__name__,
        excinfo.value.data,
    ) == snapshot()


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
