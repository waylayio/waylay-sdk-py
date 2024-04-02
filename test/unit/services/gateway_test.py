import pytest
from pytest_httpx import HTTPXMock
from typeguard import check_type

from waylay.sdk.client import WaylayClient
from waylay.sdk.services.gateway import GatewayResponse, GatewayService


def test_gateway_service_loaded(client: WaylayClient):
    """Test plugin classes are loaded."""
    assert isinstance(client.gateway, GatewayService)


@pytest.mark.asyncio
async def test_gateway_about(client: WaylayClient, httpx_mock: HTTPXMock):
    """Test gateway about status check"""
    httpx_mock.add_response(
        method="GET",
        url=client.config.gateway_url + "/",
        json={"name": "gateway", "version": "1.2.3", "health": "OK"},
        status_code=200,
    )
    client.api_client.set_options({"auth": None})
    async with client:
        resp = await client.gateway.about.get()
        check_type(resp, GatewayResponse)
