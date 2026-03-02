from __future__ import annotations

import json
from asyncio import sleep
from typing import TYPE_CHECKING

import httpx
import pytest
from sse_starlette.sse import EventSourceResponse as EventSourceStarletteResponse
from starlette.applications import Starlette
from starlette.responses import StreamingResponse as StarletteStreamingResponse
from starlette.routing import Route as StarletteRoute

from waylay.sdk.api._models import BaseModel as WaylayBaseModel
from waylay.sdk.api.client import ApiClient
from waylay.sdk.auth.model import NoCredentials
from waylay.sdk.config.model import WaylayConfig

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request as StarletteRequest

    from waylay.sdk.api.http import HttpClientOptions


@pytest.fixture(name="events", scope="session")
def _events_fixture() -> list:
    return [
        {"event": "started", "data": json.dumps({"type": "build"})},
        {"event": "completed", "data": json.dumps({"type": "build", "returnvalue": 0})},
    ]


@pytest.fixture(name="sse_app", scope="session")
def _sse_app_fixture(events: list):
    async def event_generator(events: list) -> AsyncIterator:
        for event in events:
            await sleep(0.3)
            yield event

    async def event_stream_endpoint(_request: StarletteRequest):
        generator = event_generator(events)
        return EventSourceStarletteResponse(generator)

    app = Starlette(routes=[StarletteRoute("/", endpoint=event_stream_endpoint)])
    yield app
    del app


@pytest.fixture(name="app_transport", scope="session")
async def _app_transport_fixture(sse_app):
    transport = httpx.ASGITransport(app=sse_app)
    yield transport
    await transport.aclose()


@pytest.fixture(name="config", scope="session")
def _config_fixture():
    return WaylayConfig(NoCredentials())


@pytest.fixture(name="client", scope="session")
async def _client_fixture(config, app_transport):
    http_opts: HttpClientOptions = {
        "transport": app_transport,
        "base_url": "http://test",
        "auth": None,
    }
    return ApiClient(config, http_opts)


class EventData(WaylayBaseModel):
    """Event data model."""

    type: str
    returnvalue: int


class EventModel(WaylayBaseModel):
    """Event model."""

    event: str
    data: EventData


CASES = [
    (
        "dict_events",
        {
            "response_type": dict,
            "select_path": "",
        },
    ),
    (
        "model_events",
        {
            "response_type": EventModel,
            "select_path": "",
        },
    ),
    (
        "dict_events_select_path",
        {
            "response_type": dict,
            "select_path": "data",
        },
    ),
    (
        "model_events_select_path",
        {
            "response_type": EventData,
            "select_path": "data",
        },
    ),
]


def list_to_async_iterator(lst):
    yield from lst


@pytest.mark.parametrize(
    "test_input",
    [c[1] for c in CASES],
    ids=[c[0] for c in CASES],
)
@pytest.mark.asyncio(scope="session")
async def test_iter_event_stream(test_input, client, snapshot):
    async with client:
        event_stream = await client.request(
            "GET",
            "/",
            response_type=test_input.get("response_type"),
            select_path=test_input.get("select_path"),
            stream=True,
        )
        async for event in event_stream:
            assert event == snapshot()


@pytest.fixture(name="ndjson_events", scope="session")
def _ndjson_events_fixture() -> list[dict]:
    return [
        {
            "type": "create",
            "objectType": "resource",
            "resource": {"id": "123", "name": "test"},
        },
        {
            "type": "update",
            "objectType": "resource",
            "resource": {"id": "456", "name": "test2"},
        },
    ]


@pytest.fixture(name="ndjson_app", scope="session")
def _ndjson_app_fixture(ndjson_events: list[dict]):
    async def ndjson_generator(events: list[dict]) -> AsyncIterator[str]:
        for event in events:
            await sleep(0.1)
            yield json.dumps(event) + "\n"

    async def ndjson_endpoint(_request: StarletteRequest):
        generator = ndjson_generator(ndjson_events)
        return StarletteStreamingResponse(
            generator,
            media_type="application/x-ndjson",
        )

    app = Starlette(routes=[StarletteRoute("/ndjson", endpoint=ndjson_endpoint)])
    yield app
    del app


@pytest.fixture(name="ndjson_transport", scope="session")
async def ndjson_transport_fixture(ndjson_app):
    transport = httpx.ASGITransport(app=ndjson_app)
    yield transport
    await transport.aclose()


@pytest.fixture(name="ndjson_client", scope="session")
async def ndjson_client_fixture(config, ndjson_transport):
    http_opts: HttpClientOptions = {
        "transport": ndjson_transport,
        "base_url": "http://test",
        "auth": None,
    }
    return ApiClient(config, http_opts)


class NdJsonEventModel(WaylayBaseModel):
    """NDJSON event model."""

    type: str
    objectType: str
    resource: dict


@pytest.mark.asyncio(scope="session")
async def test_ndjson_returns_parsed_dicts(ndjson_client, ndjson_events):
    """Test that NDJSON events are parsed as dict."""
    async with ndjson_client:
        event_stream = await ndjson_client.request(
            "GET",
            "/ndjson",
            response_type=dict,
            stream=True,
        )
        events = []
        async for event in event_stream:
            # The bug: event is a string, should be a dict
            assert isinstance(event, dict), (
                f"Expected dict, got {type(event).__name__}: {event!r}"
            )
            events.append(event)

        assert len(events) == 2
        assert events == ndjson_events


@pytest.mark.asyncio(scope="session")
async def test_ndjson_with_model(ndjson_client, ndjson_events):
    """Test that NDJSON events can be deserialized to Pydantic models."""
    async with ndjson_client:
        event_stream = await ndjson_client.request(
            "GET",
            "/ndjson",
            response_type=NdJsonEventModel,
            stream=True,
        )
        events = []
        async for event in event_stream:
            assert isinstance(event, NdJsonEventModel)
            events.append(event)

        assert len(events) == 2
        assert events[0].type == ndjson_events[0]["type"]
        assert events[1].type == ndjson_events[1]["type"]
