"""Base classes for Waylay REST Services."""

from waylay.api.api_client import ApiClient


class WaylayService:
    """Base Waylay service class."""

    name: str
    api_client: ApiClient

    def __init__(self, api_client: ApiClient, name=''):
        """Create a Waylay REST service."""
        self.api_client = api_client
        self.name = name

    def configure(self, api_client: ApiClient):
        """Configure the service."""
        self.api_client = api_client

class WaylayServiceStub(WaylayService):
    """Dummy Waylay service stub."""

    def __init__(self, *args, **kwargs):
        """Create an instance."""
        super().__init__(*args, **kwargs)

    def __getattr__(self, name):
        """Get attribute."""
        raise ImportError('{0} service is not installed'.format(
            self.name.capitalize() if self.name else 'This'))

    def __bool__(self):
        """Cast to boolean."""
        return False
