from asyncio import sleep
import json
from typing import AsyncIterator
import httpx
import pytest

from sse_starlette.sse import EventSourceResponse as EventSourceStarletteResponse
from starlette.applications import Starlette
from starlette.routing import Route as StarletteRoute
from starlette.requests import Request as StarletteRequest


from waylay.sdk.api.serialization import iter_event_stream
from waylay.sdk.api._models import BaseModel as WaylayBaseModel
import asyncio


@pytest.fixture(name="event_loop", scope="session")
def _event_loop_fixture():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(name="events", scope="session")
def _events_fixture() -> list:
    return [
        {"event": "started", "data": json.dumps({"type": "build"})},
        {"event": "completed", "data": json.dumps({"type": "build", "returnvalue": 0})},
    ]


@pytest.fixture(name="sse_app", scope="session")
def _sse_app_fixture(events: list, event_loop):
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
async def test_iter_event_stream(test_input, app_transport, snapshot):
    async with httpx.AsyncClient(
        transport=app_transport, base_url="http://test"
    ) as client:
        response = await client.get("/")
        event_stream = iter_event_stream(
            response,
            response_type=test_input.get("response_type"),
            select_path=test_input.get("select_path"),
        )
        async for event in event_stream:
            assert event == snapshot()
