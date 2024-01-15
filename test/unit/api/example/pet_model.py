from __future__ import annotations
import pprint
import json

from typing import Annotated, Any, ClassVar, Dict, List, NotRequired, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class Pet(BaseModel):
    """Pet."""
    name: StrictStr
    owner: PetOwner
    tag: Optional[StrictStr] = None
    __properties: ClassVar[List[str]] = ["name", "owner", "tag"]

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }

    def to_str(self) -> str:
        """Returns the string representation of the model using alias."""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Create an instance of Pet from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation."""
        _dict = self.model_dump(
            by_alias=True,
            exclude={
            },
            exclude_none=True,
        )
        if self.owner:
            _dict['owner'] = self.owner.to_dict()
        return _dict

    @classmethod
    def from_dict(cls, obj: Dict) -> Self:
        """Create an instance of Pet from a dict."""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "name": obj.get("name"),
            "owner": PetOwner.from_dict(obj.get("owner")) if obj.get("owner") is not None else None,
            "tag": obj.get("tag")
        })
        return _obj


class PetOwner(BaseModel):
    """Owner."""
    id: StrictInt
    name: StrictStr
    __properties: ClassVar[List[str]] = ["id", "name"]

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }

    def to_str(self) -> str:
        """Returns the string representation of the model using alias."""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Create an instance of Owner from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the model using alias.

        This has the following differences from calling pydantic's
        `self.model_dump(by_alias=True)`:

        * `None` is only added to the output dict for nullable fields that
          were set at model initialization. Other fields with value `None`
          are ignored.

        """
        _dict = self.model_dump(
            by_alias=True,
            exclude={
            },
            exclude_none=True,
        )
        return _dict

    @classmethod
    def from_dict(cls, obj: Dict) -> Self:
        """Create an instance of Owner from a dict."""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "id": obj.get("id"),
            "name": obj.get("name")
        })
        return _obj


class CreatePetQuery(TypedDict):
    """create_pet query parameters."""
    limit: NotRequired[Annotated[Optional[Annotated[int, Field(
        le=100, strict=True)]], Field(description="How many biscuits?")]]
    good_boy: NotRequired[Annotated[Optional[StrictBool], Field(description="Is the pet a good boy?")]]
