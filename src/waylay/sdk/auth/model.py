"""Utilities to handle waylay authentication."""

from __future__ import annotations

import abc
import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List

import jwt
from jwt.exceptions import PyJWTError

from .exceptions import AuthError, TokenParseError


class CredentialsType(str, Enum):
    """Supported Waylay Authentication Methods.

    Note that username/password authentication (as used in our IDP at
    https://login.waylay.io)
    is not (yet) supported.

    """

    CLIENT = "client_credentials"
    APPLICATION = "application_credentials"
    TOKEN = "token"
    CALLBACK = "interactive"

    def __str__(self):
        """Get the string representation."""
        return self.value


TokenString = str


class WaylayCredentials(abc.ABC):
    """Base class for the representation of credentials to the waylay platform."""

    gateway_url: str | None = None
    credentials_type: ClassVar[CredentialsType] = CredentialsType.CALLBACK

    # legacy
    accounts_url: str | None = None

    @abc.abstractmethod
    def to_dict(self, obfuscate=True) -> Dict[str, Any]:
        """Convert the credentials to a json-serialisable representation."""

    @property
    @abc.abstractmethod
    def id(self) -> str | None:
        """Get the main identifier for this credential."""
        return None

    def __repr__(self):
        """Show the implementing class and public information."""
        return f"<{self.__class__.__name__}({str(self)})>"

    def __str__(self):
        """Show the credential attributes, with secrets obfuscated."""
        return json.dumps(self.to_dict(obfuscate=True))

    @abc.abstractmethod
    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed.

        This does not assure that they will lead to a succesfull
        authentication.

        """


@dataclass(repr=False)
class CredentialsBase(WaylayCredentials):
    """Dataclass mixin for the 'gateway_url' (legacy 'accounts_url') property."""

    gateway_url: str | None = None
    accounts_url: str | None = None


@dataclass(repr=False, init=False)
class KeySecretCredentials(CredentialsBase):
    """Dataclass mixin for the 'api_key' and 'api_secret'."""

    api_key: str = ""
    api_secret: str = ""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        gateway_url: str | None = None,
        accounts_url: str | None = None,
    ):
        """Initialise with the api_key and api_secret."""
        super().__init__(gateway_url=gateway_url, accounts_url=accounts_url)
        self.api_key = api_key
        self.api_secret = api_secret

    @property
    def id(self) -> str | None:
        """Get the main identifier for this credential."""
        return self.api_key

    @classmethod
    def create(
        cls,
        api_key: str,
        api_secret: str,
        *,
        gateway_url: str | None = None,
        accounts_url: str | None = None,
    ):
        """Create a client credentials object."""
        return cls(
            api_key=api_key,
            api_secret=api_secret,
            gateway_url=gateway_url,
            accounts_url=accounts_url,
        )

    def to_dict(self, obfuscate=True):
        """Convert the credentials to a json-serialisable representation."""
        return dict(
            type=self.credentials_type.value,  # type: ignore
            api_key=self.api_key,
            api_secret="********" if obfuscate else self.api_secret,
            gateway_url=self.gateway_url,
            accounts_url=self.accounts_url,
        )

    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed.

        This does not assure that they will lead to a succesfull
        authentication.

        """
        if not (self.api_key and self.api_secret):
            return False
        # api key are 12 bytes hexc encoded
        try:
            if len(bytes.fromhex(self.api_key)) != 12:
                return False
        except ValueError:
            return False
        # api secret are 24 bytes base64 encoded (rfc4648)
        try:
            if len(base64.b64decode(self.api_secret, validate=True)) != 24:
                return False
        except binascii.Error:
            return False
        return True


@dataclass(repr=False, init=False)
class NoCredentials(CredentialsBase):
    """Credentials that be resolved via (interactive) callback when required."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.CALLBACK

    def to_dict(self, obfuscate=True):  # pylint: disable=unused-argument
        """Convert the credentials to a json-serialisable representation."""
        return dict(
            type=str(self.credentials_type),
            gateway_url=self.gateway_url,
            accounts_url=self.accounts_url,
        )

    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed."""
        return True

    @property
    def id(self) -> str | None:
        """Get the main identifier for this credential."""
        return None


@dataclass(repr=False, init=False)
class ClientCredentials(KeySecretCredentials):
    """Waylay Credentials: api key and secret of type 'client_credentials'."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.CLIENT


@dataclass(repr=False, init=False)
class ApplicationCredentials(KeySecretCredentials):
    """Waylay Credentials: api key and secret of type 'application_credentials'."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.APPLICATION
    tenant_id: str = ""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        tenant_id: str,
        *,
        gateway_url: str | None = None,
        accounts_url: str | None = None,
    ):
        """Initialise with the api_key and api_secret."""
        super().__init__(
            api_key, api_secret, gateway_url=gateway_url, accounts_url=accounts_url
        )
        self.tenant_id = tenant_id

    def to_dict(self, obfuscate=True):
        """Get the dict representation."""
        _dict = super().to_dict(obfuscate)
        _dict["tenant_id"] = self.tenant_id
        return _dict


@dataclass(repr=False, init=False)
class TokenCredentials(CredentialsBase):
    """Waylay JWT Token credentials."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.TOKEN
    token: TokenString = ""

    def __init__(
        self,
        token: TokenString,
        *,
        gateway_url: str | None = None,
        accounts_url: str | None = None,
    ):
        """Create a TokenCredentials from a token string."""
        super().__init__(gateway_url=gateway_url, accounts_url=accounts_url)
        self.token = token

    @property
    def id(self) -> str | None:
        """Get the main identifier for this credential."""
        try:
            token = WaylayToken(self.token)
            return f"[{token.domain}] {token.subject}"
        except AuthError as exc:
            return f"INVALID_TOKEN({exc})"

    def to_dict(self, obfuscate=True):
        """Get the credential attributes."""
        return dict(
            type=str(self.credentials_type),
            token="*********" if obfuscate else self.token,
            gateway_url=self.gateway_url,
            accounts_url=self.accounts_url,
        )

    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed."""
        try:
            # WaylayToken constructor decodes the data without signature verification
            return WaylayToken(self.token).tenant is not None
        except TokenParseError:
            return False


class WaylayToken:
    """Holds a Waylay JWT token."""

    def __init__(self, token_string: str, token_data: Dict | None = None):
        """Create a Waylay Token holder object from given token string or data."""
        self.token_string = token_string
        if token_data is None:
            try:
                token_data = jwt.decode(
                    token_string, options=dict(verify_signature=False)
                )
            except (TypeError, ValueError, PyJWTError) as exc:
                raise TokenParseError(exc) from exc
        self.token_data = token_data

    def validate(self) -> "WaylayToken":
        """Verify essential assertions, and its expiry state.

        This implementation does not verify the signature of a token, as
        this is seen the responsability of a server implementation.

        """
        if not self.token_string:
            raise AuthError("no token")

        if not self.token_data:
            raise AuthError("could not parse token data")

        if not self.tenant:
            raise AuthError("invalid token")

        # assert expiry
        if self.is_expired:
            raise AuthError("token expired")
        return self

    @property
    def tenant(self) -> str | None:
        """Get the tenant id asserted by the token."""
        return self.token_data.get("tenant", None)

    @property
    def domain(self) -> str | None:
        """Get the waylay domain asserted by the token."""
        return self.token_data.get("domain", None)

    @property
    def subject(self) -> str | None:
        """Get the subject asserted by the token."""
        return self.token_data.get("sub", None)

    @property
    def licenses(self) -> List[str]:
        """Get the licenses asserted by the token."""
        return self.token_data.get("licenses", [])

    @property
    def groups(self) -> List[str]:
        """Get the groups asserted by the token."""
        return self.token_data.get("groups", [])

    @property
    def permissions(self) -> List[str]:
        """Get the permissions asserted by the token."""
        return self.token_data.get("permissions", [])

    @property
    def expires_at(self) -> datetime | None:
        """Get the token expiry timestamp."""
        exp = self.token_data.get("exp", None)
        return None if exp is None else datetime.fromtimestamp(exp)

    @property
    def issued_at(self) -> datetime | None:
        """Get the token issuance timestamp."""
        iat = self.token_data.get("iat", None)
        return None if iat is None else datetime.fromtimestamp(iat)

    @property
    def expires_seconds(self) -> int:
        """Get seconds until expiry."""
        exp = self.token_data.get("exp", None)
        return 0 if exp is None else exp - datetime.now().timestamp()

    @property
    def age(self) -> int:
        """Get seconds sinds issuance."""
        iat = self.token_data.get("iat", 0)
        return int(datetime.now().timestamp() - iat)

    @property
    def is_expired(self) -> bool:
        """Get the expiration state.

        True if a (previously valid) the token has expired.

        """
        if not isinstance(self.token_data, dict):
            return True
        exp = self.expires_at
        return exp is None or exp < datetime.now()

    @property
    def is_valid(self) -> bool:
        """Get the token validity.

        True if essential token data is present and is not expired.

        """
        return (
            self.tenant is not None
            and self.subject is not None
            and self.domain is not None
            and not self.is_expired
        )

    def to_dict(self):
        """Get the main token attributes."""
        return dict(
            tenant=self.tenant,
            domain=self.domain,
            subject=self.subject,
            expires_at=str(self.expires_at),
            is_valid=self.is_valid,
        )

    def __repr__(self) -> str:
        """Show the implementing class an main attributes."""
        return f"<{self.__class__.__name__}({json.dumps(self.to_dict())})>"

    def __str__(self) -> str:
        """Render the token string."""
        return self.token_string

    def __bool__(self) -> bool:
        """Get the validity of the token."""
        return self.is_valid
