"""Test http client context managment."""
from types import SimpleNamespace
from typing import Optional

import pytest
import httpx
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from waylay.sdk import WaylayClient, WaylayService, WaylayTool, WaylayConfig
from waylay.sdk.api import AsyncClient


class MyService(WaylayService):
    """Example Service."""

    name = "tst"
    title = "Test"

    async def echo(self, message, with_http_info=False, select_path=''):
        """Echo."""
        req = self.api_client.build_api_request("POST", "/", body=message)
        resp = await self.api_client.send(req)
        if with_http_info:
            return resp
        return self.api_client.response_deserialize(resp, {}, select_path)


class MyTool(WaylayTool):
    """Example tool."""

    name = "tst_tool"
    title = "Test"
    my: MyService

    def __init__(self, *args, services, tools):
        """Create the tool."""
        super().__init__(*args, services=services, tools=tools)
        self.my = services.require(MyService)

    async def echo(self, message, with_http_info=False, select_path=''):
        """Echo."""
        return await self.my.echo(message, with_http_info, select_path)


class MyService2(MyService):
    """Example service 2."""

    name = "tst2"


@pytest.fixture(name="echo_app", scope="module")
def _fixture_my_app():
    async def echo_app(scope, receive, send):
        request = StarletteRequest(scope, receive)
        body_bytes = await request.body()
        response = StarletteResponse(
            body_bytes,
            headers={"content-type": request.headers.get("content-type", "")},
        )
        await response(scope, receive, send)

    return echo_app


@pytest.fixture(name="my_client")
def _fixture_my_client(config: WaylayConfig, echo_app):
    client = WaylayClient(
        config, {"auth": None, "transport": httpx.ASGITransport(echo_app)}
    )
    client.register(MyService)
    client.register(MyService2)
    client.register(MyTool)
    yield client


async def assert_call_echo(srv: MyService):
    """Invoke the remote service."""
    data = SimpleNamespace(message="hello world")
    api_response = await srv.echo(vars(data))
    assert data == api_response
    message = await srv.echo(vars(data), select_path='message')
    assert message == data.message
    response = await srv.echo(vars(data), with_http_info=True)
    assert response.status_code == 200
    assert response.json() == vars(data)


async def test_lazy_init(my_client: WaylayClient):
    """Test lazy initialization of http client."""
    # initial state: no http client
    init_client = my_client.api_client
    assert init_client is not None
    assert init_client.is_closed
    assert my_client.tst.api_client is init_client
    assert my_client.tst2.api_client is init_client

    # lazy create http client
    http_client: Optional[AsyncClient] = my_client.api_client.http_client
    assert my_client.api_client is init_client
    assert my_client.tst.api_client is init_client
    assert my_client.tst2.api_client is init_client
    assert http_client is not None
    assert not http_client.is_closed
    assert not my_client.api_client.is_closed
    assert my_client.api_client.http_client is http_client

    # using it does not open or close http clients
    assert my_client.tst.api_client.http_client is http_client
    assert my_client.tst2.api_client.http_client is http_client
    await assert_call_echo(my_client.tst)
    await assert_call_echo(my_client.tst2)
    await assert_call_echo(my_client.tst_tool)

    assert http_client.is_closed is False


async def test_client_ctx(my_client: WaylayClient):
    """Test client as context."""
    init_client = my_client.api_client
    assert init_client.is_closed
    # a closed api_client is initialized without replacement
    async with my_client as m:
        assert not init_client.is_closed
        assert m.api_client is init_client
        assert m.tst.api_client is init_client
        assert m.tst2.api_client is init_client
        ctx_http_client = m.api_client.http_client
        assert not ctx_http_client.is_closed
        assert m.api_client.http_client is ctx_http_client
        assert m.tst.api_client.http_client is ctx_http_client
        await assert_call_echo(m.tst)
        await assert_call_echo(m.tst2)

    assert ctx_http_client.is_closed
    assert init_client.is_closed
    assert m.tst.api_client is init_client
    assert m.tst2.api_client is init_client


def test_fail_sync_context_mgmt(my_client: WaylayClient):
    """Test error when using sync context management."""
    use_async = "Use async context management instead"
    with pytest.raises(TypeError, match=use_async):
        with my_client:
            assert False
    with pytest.raises(TypeError, match=use_async):
        with my_client.api_client:
            assert False
    with pytest.raises(TypeError, match=use_async):
        my_client.__exit__(None, None, None)
    with pytest.raises(TypeError, match=use_async):
        my_client.api_client.__exit__(None, None, None)


async def test_used_client_ctx(my_client: WaylayClient):
    """Test context management when in use."""

    # lazy init of shared api client
    tst_client = my_client.tst.api_client
    tst_http_client: httpx.AsyncClient = tst_client.http_client
    assert not tst_client.is_closed
    assert not tst_http_client.is_closed
    assert my_client.api_client is tst_client
    assert my_client.tst2.api_client is tst_client

    async with my_client.tst2 as tst2:
        # creates new api client in scope of service
        # ALT: fails (dissallow mixing of ctx mgmt and lazy init)
        # ALT: seperate state for in_cxt client and shared client.
        tst2_ctx_api_client = tst2.api_client
        assert tst2_ctx_api_client is not tst_client
        await assert_call_echo(tst2)

    # TBD: original client is not restored
    # ALT: use stack/seperate state
    assert tst2_ctx_api_client.is_closed
    assert my_client.tst2.api_client is tst2_ctx_api_client
    assert my_client.tst.api_client is tst_client
    assert my_client.api_client is tst_client

    async with my_client as m:
        # creates new api client in scope of main client
        # ALT: fails (dissallow mixing of ctx mgmt and lazy init)
        # ALT: seperate state for in_cxt client and shared client.
        assert m.api_client is not tst_client
        # TBD: new client is not copied to other services!
        # ALT: replace closed clients of all services!
        assert my_client.tst2.api_client is tst2_ctx_api_client
        assert my_client.tst.api_client is tst_client


async def test_api_client_ctx(my_client: WaylayClient):
    """Test api client context management."""
    # api clients are either reused or entered, not both:
    api_client = my_client.api_client
    assert api_client.is_closed

    # can set options on closed client.
    api_client.set_options({"timeout": 999})

    async with api_client as a:
        assert a is api_client
        assert not a.is_closed
        # cannot set options on open client.
        with pytest.raises(AttributeError, match="Cannot set options on open client"):
            api_client.set_options({"timeout": 999})

    assert a.is_closed
    # lazy init
    http_client = a.http_client
    assert http_client is not None
    assert not a.is_closed
    assert not http_client.is_closed
    assert a.http_client is http_client

    # an open api client itself is single use!
    with pytest.raises(ValueError, match="already in use"):
        async with api_client as a:
            assert False
    assert not api_client.is_closed

    # close the http client:
    await http_client.aclose()
    assert http_client.is_closed
    assert api_client.is_closed

    # context mgmt is allowed again
    async with api_client as a:
        assert not a.is_closed
    assert api_client.is_closed


async def test_reuse_config(my_client: WaylayClient):
    """Test reuse of config client."""
    new_client = WaylayClient(my_client.config)
    assert new_client.api_client is not my_client.api_client
    assert new_client.config is my_client.config
    assert "tst" in my_client.services
    # 'tst' not manually registered
    assert "tst" not in new_client.services


async def test_reuse_api_client(my_client: WaylayClient):
    """Test reuse of api client."""
    new_client = WaylayClient(my_client.api_client)
    assert new_client.api_client is my_client.api_client
    assert new_client.config is my_client.config
    assert "tst" in my_client.services
    # 'tst' not manually registered
    assert "tst" not in new_client.services


async def test_reuse_http_client(my_client: WaylayClient):
    """Test reuse of http client."""
    http_client = my_client.api_client.http_client
    assert not http_client.is_closed

    new_client = WaylayClient(my_client.config, http_client)
    assert new_client.api_client is not my_client.api_client
    assert new_client.api_client.http_client is my_client.api_client.http_client
    assert new_client.config is my_client.config
