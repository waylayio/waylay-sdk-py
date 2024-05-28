"""Gateway Service."""

from __future__ import annotations

from typing import Any, Dict, Literal, TypeVar, overload

from pydantic import ConfigDict

from waylay.sdk.api._models import BaseModel as WaylayBaseModel
from waylay.sdk.api._models import Model
from waylay.sdk.api.client import ApiClient
from waylay.sdk.api.http import HeaderTypes, QueryParamTypes, Response
from waylay.sdk.plugin.base import WaylayService, WithApiClient

T = TypeVar("T")


class GatewayService(WaylayService):
    """Gateway Service Class."""

    name = "gateway"
    title = "Gateway Service"

    about: AboutApi

    def __init__(self, api_client: ApiClient):
        """Create the gateway service."""
        super().__init__(api_client)
        self.about = AboutApi(api_client)


class AboutApi(WithApiClient):
    """About service methods."""

    @overload
    async def get(
        self,
        *,
        query: QueryParamTypes | None = None,
        raw_response: Literal[False] = False,
        select_path: Literal[""] = "",
        response_type: Literal[None] = None,
        headers: HeaderTypes | None = None,
        **kwargs,
    ) -> GatewayResponse: ...

    @overload
    async def get(
        self,
        *,
        query: QueryParamTypes | None = None,
        raw_response: Literal[False] = False,
        select_path: Literal[""] = "",
        response_type: T,
        headers: HeaderTypes | None = None,
        **kwargs,
    ) -> T: ...

    @overload
    async def get(
        self,
        *,
        query: QueryParamTypes | None = None,
        raw_response: Literal[True],
        select_path: Literal["_not_used_"] = "_not_used_",
        response_type: Literal[None] = None,  # not used
        headers: HeaderTypes | None = None,
        **kwargs,
    ) -> Response: ...

    @overload
    async def get(
        self,
        *,
        query: QueryParamTypes | None = None,
        raw_response: Literal[False] = False,
        select_path: str,
        response_type: Literal[None] = None,
        headers: HeaderTypes | None = None,
        **kwargs,
    ) -> Model: ...

    @overload
    async def get(
        self,
        *,
        query: QueryParamTypes | None = None,
        raw_response: Literal[False] = False,
        select_path: str,
        response_type: T,
        headers: HeaderTypes | None = None,
        **kwargs,
    ) -> T: ...

    async def get(
        self,
        *,
        query: QueryParamTypes | None = None,
        raw_response: bool = False,
        select_path: str = "",
        response_type: T | None = None,
        headers: HeaderTypes | None = None,
        **kwargs,
    ) -> GatewayResponse | T | Response | Model:
        """Get the status of the gateway.

        :param query: URL Query parameters.
        :type query: QueryParamTypes, optional
        :param raw_response: If true, return the http Response object instead of
            returning an api model object, or throwing an ApiError.
        :param select_path: Denotes the json path applied to the response
            object before returning it.
            Set it to the empty string `""` to receive the full response object.
        :param response_type: If specified, the response is parsed into
            an instance of the specified type.
        :param headers: Header parameters for this request
        :type headers: dict, optional
        :param `**kwargs`: Additional parameters passed on to the http client.
            See below.
        :Keyword Arguments:
            * timeout: a single numeric timeout in seconds,
                or a tuple of _connect_, _read_, _write_ and _pool_ timeouts.
            * stream: if true, the response will be in streaming mode
            * cookies
            * extensions
            * auth
            * follow_redirects: bool

        :return: Returns the result object if the http request succeeded
            with status code '2XX'.
        :raises APIError: If the http request has a status code different from `2XX`.
            This object wraps both the http Response and any parsed data.
        """
        response_type_map: Dict[str, Any] = (
            {"2XX": response_type}
            if response_type is not None
            else {
                "200": GatewayResponse if not select_path else Model,
            }
        )
        return await self.api_client.request(
            method="GET",
            resource_path="/",
            path_params={},
            params=query,
            headers=headers,
            response_type=response_type_map,
            select_path=select_path,
            raw_response=raw_response,
            **kwargs,
        )


class GatewayResponse(WaylayBaseModel):
    """Gateway status response."""

    name: str
    version: str
    health: str

    model_config = ConfigDict(
        populate_by_name=True,
        protected_namespaces=(),
        extra="allow",
    )
