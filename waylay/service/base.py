from waylay.api.api_client import ApiClient


class WaylayService:
    """Base Waylay service class."""

    name: str
    api_client: ApiClient

    def __init__(self, api_client: ApiClient, name=''):
        self.api_client = api_client
        self.name = name

    def configure(self, api_client: ApiClient):
        self.api_client = api_client


class WaylayServiceStub(WaylayService):
    """Dummy Waylay service stub."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, name):
        raise ImportError('{0} service is not installed'.format(
            self.name.capitalize() if self.name else 'This'))

    def __bool__(self):
        return False
