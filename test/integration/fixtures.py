"""Reusable test fixtures."""
import os

import pytest

from waylay import ClientCredentials, WaylayClient
from waylay.auth import WaylayCredentials, WaylayTokenAuth


def get_test_env(key: str, default: str = None) -> str:
    """Get an environment variable."""
    test_var = os.getenv(key, default)
    if not test_var:
        raise AttributeError(f'{key} environment variable not configured, while test requires it.')
    return test_var


@pytest.fixture(scope='session')
def waylay_test_user_id():
    """Get environment variable WAYLAY_TEST_USER_ID."""
    return get_test_env('WAYLAY_TEST_USER_ID')


@pytest.fixture(scope='session')
def waylay_test_user_secret():
    """Get environment variable WAYLAY_TEST_USER_SECRET."""
    return get_test_env('WAYLAY_TEST_USER_SECRET')


@pytest.fixture(scope='session')
def waylay_test_accounts_url():
    """Get environment variable WAYLAY_TEST_ACCOUNTS_URL or 'https://accounts-api-aws.dev.waylay.io'."""
    return get_test_env('WAYLAY_TEST_ACCOUNTS_URL', 'https://accounts-api-aws.dev.waylay.io')


@pytest.fixture(scope='session')
def waylay_test_gateway_url():
    """Get environment variable WAYLAY_TEST_GATEWAY_URL or 'https://api-aws-dev.waylay.io'."""
    return get_test_env('WAYLAY_TEST_GATEWAY_URL', 'https://api-aws-dev.waylay.io')


@pytest.fixture(scope='session')
def waylay_test_client_credentials(waylay_test_user_id, waylay_test_user_secret, waylay_test_gateway_url):
    """Get client credentials.

    As specified in the environment variables
    WAYLAY_TEST_USER_ID, WAYLAY_TEST_USER_SECRET, WAYLAY_TEST_GATEWAY_URL
    """
    return ClientCredentials(
        waylay_test_user_id, waylay_test_user_secret, gateway_url=waylay_test_gateway_url
    )


@pytest.fixture(scope='session')
def waylay_test_token_string(waylay_test_client_credentials):
    """Get a valid token string."""
    token = WaylayTokenAuth(waylay_test_client_credentials).assure_valid_token()
    return token.token_string


def _create_client_from_profile_or_creds(credentials: WaylayCredentials) -> WaylayClient:
    profile = os.getenv('WAYLAY_TEST_PROFILE')
    if profile:
        return WaylayClient.from_profile(profile)
    else:
        return WaylayClient.from_credentials(credentials)


@pytest.fixture(scope='session')
def waylay_session_test_client(waylay_test_client_credentials: WaylayCredentials):
    """Get a test waylay SDK client (same for whole session)."""
    return _create_client_from_profile_or_creds(waylay_test_client_credentials)


@pytest.fixture
def waylay_test_client(waylay_test_client_credentials: WaylayCredentials):
    """Get a test waylay SDK client."""
    return _create_client_from_profile_or_creds(waylay_test_client_credentials)
