"""Httpx Authentication provider."""

from typing import Optional, Callable, AsyncGenerator

import httpx

from .model import (
    WaylayCredentials,
    WaylayToken,
    TokenString,
    TokenCredentials,
    NoCredentials,
    ApplicationCredentials,
    ClientCredentials,
)
from .exceptions import AuthError


CredentialsCallback = Callable[[Optional[str]], WaylayCredentials]


class WaylayTokenAuth(httpx.Auth):
    """Authentication flow with a waylay token.

    Will automatically refresh an expired token.

    """

    current_token: Optional[WaylayToken]
    credentials: WaylayCredentials
    http_client: Optional[httpx.AsyncClient]

    def __init__(
        self,
        credentials: WaylayCredentials,
        initial_token: Optional[TokenString] = None,
        credentials_callback: Optional[CredentialsCallback] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        """Create a Waylay Token authentication provider."""
        self.credentials = credentials
        self.current_token = None
        self.http_client = http_client

        if isinstance(credentials, TokenCredentials):
            initial_token = initial_token or credentials.token

        if initial_token:
            try:
                self.current_token = self._create_and_validate_token(initial_token)
            except AuthError:
                pass

        self.credentials_callback = credentials_callback

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """Authenticate a http request.

        Implements the authentication callback for the http client.

        """
        token = await self.assure_valid_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

    async def assure_valid_token(self) -> WaylayToken:
        """Validate the current token and request a new one if invalid."""
        if self.current_token:
            # token exists and is valid
            return self.current_token

        self.current_token = self._create_and_validate_token(
            await self._request_token_string()
        )
        return self.current_token

    def _create_and_validate_token(self, token: TokenString) -> WaylayToken:
        return WaylayToken(token).validate()

    async def _request_token_string(self) -> TokenString:
        """Request a token."""
        if isinstance(self.credentials, NoCredentials):
            if self.credentials_callback is not None:
                self.credentials = self.credentials_callback(
                    self.credentials.accounts_url or self.credentials.gateway_url
                )
            else:
                raise AuthError("No credentials or credentials_callback provided.")

        if isinstance(self.credentials, TokenCredentials):
            raise AuthError(
                f"cannot refresh expired token with credentials "
                f"of type '{self.credentials.credentials_type}'"
            )

        if isinstance(self.credentials, ApplicationCredentials):
            raise AuthError(
                f"credentials of type {self.credentials.credentials_type} are not supported yet"
            )

        if isinstance(self.credentials, ClientCredentials):
            return await self._request_token(self.credentials)

        raise AuthError(
            f"credentials of type {self.credentials.credentials_type} are not supported"
        )

    async def _request_token(self, credentials: ClientCredentials) -> str:
        token_url_prefix = (
            credentials.accounts_url or f"{credentials.gateway_url}/accounts/v1"
        )
        token_url = f"{token_url_prefix}/tokens?grant_type=client_credentials"
        token_req = {
            "clientId": credentials.api_key,
            "clientSecret": credentials.api_secret,
        }
        try:
            if self.http_client:
                token_resp = await self.http_client.post(url=token_url, json=token_req)
            else:
                token_resp = httpx.post(url=token_url, json=token_req)
            if token_resp.status_code != 200:
                raise AuthError(
                    f"could not obtain waylay token: {token_resp.content!r} [{token_resp.status_code}]"
                )
            token_resp_json = token_resp.json()
        except httpx.HTTPError as exc:
            raise AuthError(f"could not obtain waylay token: {exc}") from exc
        return token_resp_json["token"]
