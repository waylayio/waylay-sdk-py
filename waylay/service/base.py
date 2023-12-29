from waylay.api.api_client import ApiClient


class WaylayService:
    """Base Waylay service class."""

    api_client: ApiClient

    def __init__(self, api_client: ApiClient):
        self.api_client = api_client

    def configure(self, api_client: ApiClient):
        self.api_client = api_client

class WaylayServiceStub(WaylayService):
    """Dummy Waylay service stub."""

    message: str

    def __init__(self, api_client: ApiClient, message):
        super().__init__(api_client)
        self.message = message

    def __getattr__(self, name):
        raise ImportError(self.message)

    def __bool__(self):
        return False