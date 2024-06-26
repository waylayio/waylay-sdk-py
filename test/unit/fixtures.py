"""Shared unit test fixtures."""

from datetime import datetime

import pytest

from waylay.sdk import WaylayClient, WaylayConfig
from waylay.sdk.auth import NoCredentials, WaylayToken

MOCK_DOMAIN = "unittest.waylay.io"
MOCK_API_URL = f"https://{MOCK_DOMAIN}/api"

MOCK_TENANT_SETTINGS = {"waylay_api": MOCK_API_URL, "waylay_domain": MOCK_DOMAIN}

MOCK_TOKEN_DATA = {
    "domain": MOCK_DOMAIN,
    "tenant": "9999999999999999999999",
    "sub": "users/999999999999999",
    "exp": datetime.now().timestamp() + 100000,
}


class WaylayTokenStub(WaylayToken):
    """A WaylayToken test stub with fixed data."""

    def __init__(self):
        """Create a WaylayTokenStub."""
        super().__init__("", MOCK_TOKEN_DATA)


@pytest.fixture(name="credentials")
def _fixture_credentials():
    yield NoCredentials(gateway_url="http://test")


@pytest.fixture(name="config")
def _fixture_config(credentials):
    yield WaylayConfig(credentials)


@pytest.fixture(name="client")
def _fixture_client(config):
    yield WaylayClient(config)
