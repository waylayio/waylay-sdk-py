"""Httpx Authentication provider."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Callable, Generator, Optional

import httpx

from .exceptions import AuthError
from .model import (
    ApplicationCredentials,
    ClientCredentials,
    KeySecretCredentials,
    NoCredentials,
    TokenCredentials,
    TokenString,
    WaylayCredentials,
    WaylayToken,
)

CredentialsCallback = Callable[[Optional[str]], WaylayCredentials]


class WaylayTokenAuth(httpx.Auth):
    """Authentication flow with a waylay token.

    Will automatically refresh an expired token.
    """

    AUTH_EXCEPTION = AuthError
    current_token: WaylayToken | None
    credentials: WaylayCredentials
    http_client_sync: httpx.Client
    http_client_async: httpx.AsyncClient

    def __init__(
        self,
        credentials: WaylayCredentials,
        credentials_callback: CredentialsCallback | None = None,
        http_client: httpx.AsyncClient | httpx.Client | None = None,
    ):
        """Create a Waylay Token authentication provider."""
        self.credentials = credentials
        self.current_token = None
        self.http_client_sync = (
            http_client if isinstance(http_client, httpx.Client) else httpx.Client()
        )
        self.http_client_async = (
            http_client
            if isinstance(http_client, httpx.AsyncClient)
            else httpx.AsyncClient()
        )
        self.credentials_callback = credentials_callback

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """Authenticate a http request asynchronously."""
        token = await self.assure_valid_token_async()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

    def sync_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Authenticate a http request synchronously."""
        token = self.assure_valid_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

    def assure_valid_token(self) -> WaylayToken:
        """Validate the current token and request a new one if invalid."""
        if self.current_token and self.current_token.is_valid:
            return self.current_token
        credentials = self._validate_credentials()
        if isinstance(credentials, TokenCredentials):
            token_str = credentials.token
        else:
            token_str = self._request_token_sync(credentials)
        self.current_token = self._create_and_validate_token_sync(token_str)
        return self.current_token

    async def assure_valid_token_async(self) -> WaylayToken:
        """Validate the current token and request a new one if invalid."""
        if self.current_token and self.current_token.is_valid:
            return self.current_token
        credentials = self._validate_credentials()
        if isinstance(credentials, TokenCredentials):
            token_str = credentials.token
        else:
            token_str = await self._request_token_async(credentials)
        self.current_token = await self._create_and_validate_token_async(token_str)
        return self.current_token

    def _create_and_validate_token_sync(self, token: TokenString) -> WaylayToken:
        return WaylayToken(token).validate()

    async def _create_and_validate_token_async(self, token: TokenString) -> WaylayToken:
        return self._create_and_validate_token_sync(token)

    def _validate_credentials(self) -> KeySecretCredentials | TokenCredentials:
        if isinstance(self.credentials, NoCredentials):
            if self.credentials_callback is not None:
                self.credentials = self.credentials_callback(
                    self.credentials.accounts_url or self.credentials.gateway_url
                )
            else:
                raise self.AUTH_EXCEPTION(
                    "No credentials or credentials_callback provided."
                )
        if isinstance(self.credentials, (KeySecretCredentials, TokenCredentials)):
            return self.credentials
        raise self.AUTH_EXCEPTION(
            f"credentials of type {self.credentials.credentials_type} are not supported"
        )

    def _token_request(self, credentials: KeySecretCredentials) -> httpx.Request:
        http_client = self.http_client_async or self.http_client_sync
        token_url_prefix = (
            credentials.accounts_url or f"{credentials.gateway_url}/accounts/v1"
        )
        if isinstance(credentials, ClientCredentials):
            url = f"{token_url_prefix}/tokens"
            params = {"grant_type": "client_credentials"}
            json = {
                "clientId": credentials.api_key,
                "clientSecret": credentials.api_secret,
            }
            return http_client.build_request("POST", url, params=params, json=json)
        if isinstance(credentials, ApplicationCredentials):
            url = f"{token_url_prefix}/tokens"
            params = {
                "grant_type": "application_credentials",
                "tenant": credentials.tenant_id,
            }
            json = {
                "applicationId": credentials.api_key,
                "applicationSecret": credentials.api_secret,
            }
            return http_client.build_request("POST", url, params=params, json=json)
        raise self.AUTH_EXCEPTION(
            f"credentials of type {self.credentials.credentials_type} "
            "are not supported."
        )

    def _parse_token_response(self, response: httpx.Response) -> str:
        try:
            response.raise_for_status()
            token_resp_json = response.json()
            return token_resp_json["token"]
        except httpx.HTTPError as exc:
            raise self.AUTH_EXCEPTION("Could not obtain waylay token") from exc

    def _request_token_sync(self, credentials: KeySecretCredentials) -> str:
        return self._parse_token_response(
            self.http_client_sync.send(self._token_request(credentials))
        )

    async def _request_token_async(self, credentials: KeySecretCredentials) -> str:
        return self._parse_token_response(
            await self.http_client_async.send(self._token_request(credentials))
        )
