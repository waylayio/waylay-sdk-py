"""Utilities to handle waylay authentication."""

from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import (
    Optional, Generator, ClassVar,
    Dict, Any, List, Callable,
)
import json
import abc

import base64
import binascii
import httpx
from jose import jwt, JWTError
import jose.exceptions as jwt_exc

from .exceptions import AuthError

# http client dependencies
_http = httpx


class CredentialsType(str, Enum):
    """Supported Waylay Authentication Methods.

    Note that username/password authentication (as used in our IDP at https://login.waylay.io)
    is not (yet) supported.
    """

    CLIENT = 'client_credentials'
    APPLICATION = 'application_credentials'
    TOKEN = 'token'
    CALLBACK = 'interactive'

    def __str__(self):
        """Get the string representation."""
        return self.value


DEFAULT_GATEWAY_URL = 'https://api.waylay.io'
DEFAULT_ACCOUNTS_URL = 'https://accounts-api.waylay.io'

ACCOUNTS_USERS_ME_PATH = '/accounts/v1/users/me'

TokenString = str


class WaylayCredentials(abc.ABC):
    """Base class for the representation of credentials to the waylay platform."""

    gateway_url: Optional[str] = None
    credentials_type: ClassVar[CredentialsType] = CredentialsType.CALLBACK

    # legacy
    accounts_url: Optional[str] = None

    @abc.abstractmethod
    def to_dict(self, obfuscate=True) -> Dict[str, Any]:
        """Convert the credentials to a json-serialisable representation."""

    @abc.abstractproperty
    def id(self) -> Optional[str]:
        """Get the main identifier for this credential."""
        return None

    def __repr__(self):
        """Show the implementing class and public information."""
        return f'<{self.__class__.__name__}({str(self)})>'

    def __str__(self):
        """Show the credential attributes, with secrets obfuscated."""
        return json.dumps(self.to_dict(obfuscate=True))

    @abc.abstractmethod
    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed.

        This does not assure that they will lead to a succesfull authentication.
        """


CredentialsCallback = Callable[[Optional[str]], WaylayCredentials]


@dataclass(repr=False)
class AccountsUrlMixin:
    """Dataclass mixin for the 'gateway_url' (legacy 'accounts_url') property."""

    gateway_url: Optional[str] = None
    accounts_url: Optional[str] = None


@dataclass(repr=False, init=False)
class ApiKeySecretMixin(AccountsUrlMixin):
    """Dataclass mixin for the 'api_key' and 'api_secret'."""

    api_key: str = ''
    api_secret: str = ''

    def __init__(
        self, api_key: str, api_secret: str,
        *, gateway_url: Optional[str] = None, accounts_url: Optional[str] = None
    ):
        """Initialise with the api_key and api_secret."""
        super().__init__(gateway_url=gateway_url, accounts_url=accounts_url)
        self.api_key = api_key
        self.api_secret = api_secret

    @property
    def id(self) -> Optional[str]:
        """Get the main identifier for this credential."""
        return self.api_key

    @classmethod
    def create(
        cls, api_key: str, api_secret: str,
        *, gateway_url: Optional[str] = None, accounts_url: Optional[str] = None
    ):
        """Create a client credentials object."""
        return cls(
            api_key=api_key, api_secret=api_secret, gateway_url=gateway_url, accounts_url=accounts_url
        )

    def to_dict(self, obfuscate=True):
        """Convert the credentials to a json-serialisable representation."""
        return dict(
            type=self.credentials_type.value,
            api_key=self.api_key,
            api_secret='********' if obfuscate else self.api_secret,
            gateway_url=self.gateway_url,
            accounts_url=self.accounts_url
        )

    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed.

        This does not assure that they will lead to a succesfull authentication.
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
class NoCredentials(AccountsUrlMixin, WaylayCredentials):
    """Represents that credentials can be asked via (interactive) callback when required."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.CALLBACK

    def to_dict(self, obfuscate=True):  # pylint: disable=unused-argument
        """Convert the credentials to a json-serialisable representation."""
        return dict(
            type=str(self.credentials_type),
            gateway_url=self.gateway_url,
            accounts_url=self.accounts_url
        )

    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed."""
        return True

    @property
    def id(self) -> Optional[str]:
        """Get the main identifier for this credential."""
        return None


@dataclass(repr=False, init=False)
class ClientCredentials(ApiKeySecretMixin, WaylayCredentials):
    """Waylay Credentials: api key and secret of type 'client_credentials'."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.CLIENT


@dataclass(repr=False, init=False)
class ApplicationCredentials(ApiKeySecretMixin, WaylayCredentials):
    """Waylay Credentials: api key and secret of type 'application_credentials'."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.APPLICATION
    tenant_id: str = ''


@dataclass(repr=False, init=False)
class TokenCredentials(AccountsUrlMixin, WaylayCredentials):
    """Waylay JWT Token credentials."""

    credentials_type: ClassVar[CredentialsType] = CredentialsType.TOKEN
    token: TokenString = ''

    def __init__(
        self, token: TokenString,
        *, gateway_url: Optional[str] = None, accounts_url: Optional[str] = None
    ):
        """Create a TokenCredentials from a token string."""
        super().__init__(gateway_url=gateway_url, accounts_url=accounts_url)
        self.token = token

    @property
    def id(self) -> Optional[str]:
        """Get the main identifier for this credential."""
        try:
            token = WaylayToken(self.token)
            return f'[{token.domain}] {token.subject}'
        except AuthError as exc:
            return f'INVALID_TOKEN({exc})'

    def to_dict(self, obfuscate=True):
        """Get the credential attributes."""
        return dict(
            type=str(self.credentials_type),
            token='*********' if obfuscate else self.token,
            gateway_url=self.gateway_url,
            accounts_url=self.accounts_url
        )

    def is_well_formed(self) -> bool:
        """Validate that these credentials are well-formed."""
        try:
            # WaylayToken constructor decodes the data without signature verification
            return WaylayToken(self.token).tenant is not None
        except AuthError:
            return False


class WaylayToken:
    """Holds a Waylay JWT token."""

    def __init__(self, token_string: str, token_data: Optional[Dict] = None):
        """Create a Waylay Token holder object from given token string or data."""
        self.token_string = token_string
        if token_data is None:
            try:
                token_data = jwt.decode(token_string, None, options=dict(verify_signature=False))
            except (TypeError, ValueError, JWTError) as exc:
                raise AuthError(_auth_message_for_exception(exc)) from exc
        self.token_data = token_data

    def validate(self) -> 'WaylayToken':
        """Verify essential assertions, and its expiry state.

        This implementation does not verify the signature of a token,
        as this is seen the responsability of a server implementation.
        """
        if not self.token_string:
            raise AuthError('no token')

        if not self.token_data:
            raise AuthError('could not parse token data')

        if not self.tenant:
            raise AuthError('invalid token')

        # assert expiry
        if self.is_expired:
            raise AuthError('token expired')
        return self

    @property
    def tenant(self) -> Optional[str]:
        """Get the tenant id asserted by the token."""
        return self.token_data.get('tenant', None)

    @property
    def domain(self) -> Optional[str]:
        """Get the waylay domain asserted by the token."""
        return self.token_data.get('domain', None)

    @property
    def subject(self) -> Optional[str]:
        """Get the subject asserted by the token."""
        return self.token_data.get('sub', None)

    @property
    def licenses(self) -> List[str]:
        """Get the licenses asserted by the token."""
        return self.token_data.get('licenses', [])

    @property
    def groups(self) -> List[str]:
        """Get the groups asserted by the token."""
        return self.token_data.get('groups', [])

    @property
    def permissions(self) -> List[str]:
        """Get the permissions asserted by the token."""
        return self.token_data.get('permissions', [])

    @property
    def expires_at(self) -> Optional[datetime]:
        """Get the token expiry timestamp."""
        exp = self.token_data.get('exp', None)
        return None if exp is None else datetime.fromtimestamp(exp)

    @property
    def issued_at(self) -> Optional[datetime]:
        """Get the token issuance timestamp."""
        iat = self.token_data.get('iat', None)
        return None if iat is None else datetime.fromtimestamp(iat)

    @property
    def expires_seconds(self) -> int:
        """Get seconds until expiry."""
        exp = self.token_data.get('exp', None)
        return 0 if exp is None else exp - datetime.now().timestamp()

    @property
    def age(self) -> int:
        """Get seconds sinds issuance."""
        iat = self.token_data.get('iat', 0)
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
            is_valid=self.is_valid
        )

    def __repr__(self) -> str:
        """Show the implementing class an main attributes."""
        return f'<{self.__class__.__name__}({json.dumps(self.to_dict())})>'

    def __str__(self) -> str:
        """Render the token string."""
        return self.token_string

    def __bool__(self) -> bool:
        """Get the validity of the token."""
        return self.is_valid


class WaylayTokenAuth(_http.Auth):
    """Authentication flow with a waylay token.

    Will automatically refresh an expired token.
    """

    current_token: Optional[WaylayToken]
    credentials: WaylayCredentials

    def __init__(
        self,
        credentials: WaylayCredentials,
        initial_token: Optional[TokenString] = None,
        credentials_callback: Optional[CredentialsCallback] = None
    ):
        """Create a Waylay Token authentication provider."""
        self.credentials = credentials
        self.current_token = None

        if isinstance(credentials, TokenCredentials):
            initial_token = initial_token or credentials.token

        if initial_token:
            try:
                self.current_token = self._create_and_validate_token(initial_token)
            except AuthError:
                pass

        self.credentials_callback = credentials_callback

    def auth_flow(self, request: _http.Request) -> Generator[_http.Request,  _http.Response, None]:
        """Authenticate a http request.

        Implements the authentication callback for the http client.
        """
        token = self.assure_valid_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

    def assure_valid_token(self) -> WaylayToken:
        """Validate the current token and request a new one if invalid."""
        if self.current_token:
            # token exists and is valid
            return self.current_token

        self.current_token = self._create_and_validate_token(self._request_token_string())
        return self.current_token

    def _create_and_validate_token(self, token: TokenString) -> WaylayToken:
        return WaylayToken(token).validate()

    def _request_token_string(self) -> TokenString:
        """Request a token."""
        if isinstance(self.credentials, NoCredentials):
            if self.credentials_callback is not None:
                # TODO: where is this used? Clients need to update their
                # definition of the callback to use gateway URL as argument.
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
            return _request_token(self.credentials)

        raise AuthError(
            f"credentials of type {self.credentials.credentials_type} are not supported"
        )


def _request_token(credentials: ClientCredentials) -> str:
    token_url_prefix = credentials.accounts_url or f'{credentials.gateway_url}/accounts/v1'
    token_url = f"{token_url_prefix}/tokens?grant_type=client_credentials"
    token_req = {
        'clientId': credentials.api_key,
        'clientSecret': credentials.api_secret,
    }
    try:
        token_resp = _http.post(url=token_url, json=token_req)
        if token_resp.status_code != 200:
            raise AuthError(f'could not obtain waylay token: {token_resp.content!r} [{token_resp.status_code}]')
        token_resp_json = token_resp.json()
    except _http.HTTPError as exc:
        raise AuthError(f'could not obtain waylay token: {exc}') from exc
    return token_resp_json['token']


_AUTH_MESSAGE_FOR_EXCEPTON_CLASS = [
    (jwt_exc.JWTClaimsError, 'invalid token'),
    (jwt_exc.ExpiredSignatureError, 'token expired'),
    (jwt_exc.JWTError, 'invalid token'),
    (TypeError, 'could not decode token'),
    (ValueError, 'could not decode token')
]


def _auth_message_for_exception(exception):
    for (exc_class, msg) in _AUTH_MESSAGE_FOR_EXCEPTON_CLASS:
        if isinstance(exception, exc_class):
            return msg
    return 'could not decode token'


def parse_credentials(json_obj: Dict[str, Any]) -> WaylayCredentials:
    """Convert a parsed json representation to a WaylayCredentials object."""
    cred_type = json_obj.get('type', None)
    if cred_type is None:
        raise ValueError('invalid json for credentials: missing type')

    for clz in [NoCredentials, ClientCredentials, ApplicationCredentials, TokenCredentials]:
        if clz.credentials_type == cred_type:  # type: ignore
            return clz(**{k: v for k, v in json_obj.items() if k != 'type'})

    raise ValueError(f'cannot parse json for credential type {cred_type}')
