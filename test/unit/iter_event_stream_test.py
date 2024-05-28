import json
from asyncio import sleep
from collections.abc import AsyncIterator

import httpx
import pytest
from sse_starlette.sse import EventSourceResponse as EventSourceStarletteResponse
from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest
from starlette.routing import Route as StarletteRoute

from waylay.sdk.api._models import BaseModel as WaylayBaseModel
from waylay.sdk.api.client import ApiClient
from waylay.sdk.api.http import HttpClientOptions
from waylay.sdk.auth.model import NoCredentials
from waylay.sdk.config.model import WaylayConfig


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

    async def event_stream_endpoint(request: StarletteRequest):
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
    yield WaylayConfig(NoCredentials())


@pytest.fixture(name="client", scope="session")
async def _client_fixture(config, app_transport):
    http_opts: HttpClientOptions = {
        "transport": app_transport,
        "base_url": "http://test",
        "auth": None,
    }
    yield ApiClient(config, http_opts)


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
    for item in lst:
        yield item


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
