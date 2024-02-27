"""Test plugin system."""

import pytest

from waylay.sdk import WaylayService, WaylayTool, WaylayClient

sdk_test = pytest.importorskip("waylay.sdk_test", reason="Test plugin not installed.")
ExampleService = sdk_test.ExampleService
ExampleTool = sdk_test.ExampleTool


def test_plugin_present():
    """Test plugin classes are present."""
    assert ExampleService.name == "exampleService"
    assert ExampleTool.name == "exampleTool"


def test_plugin_loaded(client: WaylayClient):
    """Test plugin classes are loaded."""
    assert isinstance(client.exampleService, ExampleService)
    assert isinstance(client.exampleTool, ExampleTool)


def test_service_access(client: WaylayClient):
    """Test service plugin access methods."""
    srv = client.exampleService
    name = client.exampleService.name
    assert name == "exampleService"
    assert srv == client.services[name]
    assert srv == client.services.exampleService
    assert srv == client.services.select(ExampleService)
    assert srv == client.services.select(ExampleService, name=name)
    assert srv == client.services.select(WaylayService, name=name)
    assert srv == client.services.require(ExampleService)
    assert srv == client.services.require(ExampleService, name=name)
    assert srv == client.services.require(WaylayService, name=name)
    assert srv in client.services.values()
    assert name in client.services
    assert name in client.services.keys()


def test_tool_access(client: WaylayClient):
    """Test tool plugin access methods."""
    tool = client.exampleTool
    name = client.exampleTool.name
    assert name == "exampleTool"
    assert tool == client.tools[name]
    assert tool == client.tools.exampleTool
    assert tool == client.tools.select(ExampleTool)
    assert tool == client.tools.select(ExampleTool, name=name)
    assert tool == client.tools.select(ExampleTool, name=name)
    assert tool == client.tools.require(ExampleTool)
    assert tool == client.tools.require(ExampleTool, name=name)
    assert tool == client.tools.require(WaylayTool, name=name)
    assert tool in client.tools.values()
    assert name in client.tools
    assert name in client.tools.keys()


class MyService(WaylayService):
    """Dummy Service."""

    name = "my_service"
    title = "Dynamic Test Service"


class MyOtherService(WaylayService):
    """Dummy Service."""

    name = "my_service"
    title = "Replacement Test Service"


def test_repr(client: WaylayClient):
    """Test string representations."""
    srv = MyOtherService(client.api_client)
    assert str(srv) == "my_service: Replacement Test Service"
    assert repr(srv) == "<MyOtherService(my_service)>"
    assert "services=[exampleService],tools=[exampleTool]" in repr(client)
    assert (
        repr(client.services) == "{'exampleService': <ExampleService(exampleService)>}"
    )
    assert repr(client.tools) == "{'exampleTool': <ExampleTool(exampleTool)>}"


def test_register(client: WaylayClient):
    """Test register an additional plugin."""
    my_name = "my_service"
    with pytest.raises(AttributeError):
        assert client.my_service
    assert my_name not in client.services
    assert client.services.select(MyService) is None
    assert client.services.select(MyOtherService) is None
    assert client.services.select(WaylayService, name=my_name) is None

    with pytest.raises(AttributeError):
        assert client.services.require(MyService)
    with pytest.raises(AttributeError):
        assert client.services.require(MyOtherService)
    with pytest.raises(AttributeError):
        assert client.services.require(WaylayService, name=my_name)

    srv_cnt = len(client.services)
    srv = client.register(MyService)
    assert len(client.services) == srv_cnt + 1
    assert isinstance(srv, MyService)
    assert client.my_service is srv
    assert client.services.require(MyService) is srv
    assert client.services.require(WaylayService, name=my_name) is srv
    assert client.services.select(MyOtherService) is None

    # replace plugin with same name
    other_srv = client.register(MyOtherService)
    assert len(client.services) == srv_cnt + 1
    assert isinstance(other_srv, MyOtherService)
    assert client.my_service == other_srv
    assert client.services.require(MyOtherService) is other_srv
    assert client.services.require(WaylayService, name=my_name) is other_srv
    assert client.services.select(MyService) is None

    assert "services=[exampleService,my_service],tools=[exampleTool]" in repr(client)
    assert repr(client.services) == (
        "{"
        "'exampleService': <ExampleService(exampleService)>, "
        "'my_service': <MyOtherService(my_service)>"
        "}"
    )


class NotAService:
    """Dummy Service."""

    name = "my_service"
    title = "Not a Test Service"


def test_register_not_a_service(client: WaylayClient):
    """Test invalid registrations."""
    with pytest.warns(match="Invalid plug class"):
        assert client.register(NotAService) is None  # type: ignore
